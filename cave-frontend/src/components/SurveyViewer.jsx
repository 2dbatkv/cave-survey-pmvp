import { useState, useEffect } from "react";
import { getSurveyData, reduceSurvey, getSurveyPlot, exportSurvey } from "../api";

export default function SurveyViewer({ surveyId, onClose }) {
  const [surveyData, setSurveyData] = useState(null);
  const [reduction, setReduction] = useState(null);
  const [plotUrl, setPlotUrl] = useState(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState(null);
  const [exportStatus, setExportStatus] = useState("");

  useEffect(() => {
    loadSurveyData();
  }, [surveyId]);

  const loadSurveyData = async () => {
    try {
      setLoading(true);
      const data = await getSurveyData(surveyId);
      setSurveyData(data);
      setError(null);
    } catch (err) {
      setError(err.message || "Failed to load survey data");
    } finally {
      setLoading(false);
    }
  };

  const handleReduce = async () => {
    try {
      setProcessing(true);
      setError(null);
      const result = await reduceSurvey(surveyId);
      setReduction(result);
      setProcessing(false);
    } catch (err) {
      setError(err.message || "Failed to reduce survey");
      setProcessing(false);
    }
  };

  const handlePlot = async () => {
    try {
      setProcessing(true);
      setError(null);
      const url = await getSurveyPlot(surveyId);
      setPlotUrl(url);
      setProcessing(false);
    } catch (err) {
      setError(err.message || "Failed to generate plot");
      setProcessing(false);
    }
  };

  const handleExport = async (format) => {
    try {
      setExportStatus(`Exporting ${format.toUpperCase()}...`);
      await exportSurvey(surveyId, format);
      setExportStatus(`✓ ${format.toUpperCase()} exported successfully!`);
      setTimeout(() => setExportStatus(""), 3000);
    } catch (err) {
      setExportStatus(`✗ Export failed: ${err.message}`);
      setTimeout(() => setExportStatus(""), 5000);
    }
  };

  if (loading) {
    return <div style={styles.container}>Loading survey data...</div>;
  }

  if (error && !surveyData) {
    return (
      <div style={styles.container}>
        <div style={styles.error}>{error}</div>
        <button style={styles.button} onClick={onClose}>
          Back
        </button>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <div>
          <h2>{surveyData?.survey_name || "Survey"}</h2>
          <p style={{ color: "#666", margin: "5px 0" }}>
            Section: {surveyData?.section || "main"} |
            {" "}{surveyData?.survey_shots || 0} survey shots |
            {" "}{surveyData?.splays || 0} splays
          </p>
        </div>
        <button style={styles.closeButton} onClick={onClose}>
          ✕ Close
        </button>
      </div>

      {error && (
        <div style={styles.error}>
          {error}
        </div>
      )}

      {/* Actions Section */}
      <div style={styles.section}>
        <h3>Survey Processing</h3>
        <div style={styles.actionButtons}>
          <button
            style={styles.primaryButton}
            onClick={handleReduce}
            disabled={processing || !surveyData?.survey_shots}
          >
            {processing ? "Processing..." : "🔢 Reduce Survey"}
          </button>

          <button
            style={styles.primaryButton}
            onClick={handlePlot}
            disabled={processing || !surveyData?.survey_shots}
          >
            {processing ? "Plotting..." : "📊 Generate Plot"}
          </button>
        </div>

        <p style={{ fontSize: "14px", color: "#666", marginTop: "10px" }}>
          Reduce calculates 3D station positions. Plot generates a visual line drawing.
        </p>
      </div>

      {/* Reduction Results */}
      {reduction && (
        <div style={styles.section}>
          <h3>Reduction Results</h3>
          <div style={styles.stats}>
            <div style={styles.statBox}>
              <div style={styles.statValue}>{reduction.num_stations}</div>
              <div style={styles.statLabel}>Stations</div>
            </div>
            <div style={styles.statBox}>
              <div style={styles.statValue}>{reduction.num_shots}</div>
              <div style={styles.statLabel}>Shots</div>
            </div>
            <div style={styles.statBox}>
              <div style={styles.statValue}>{reduction.total_distance?.toFixed(1)}</div>
              <div style={styles.statLabel}>Total Distance (ft)</div>
            </div>
          </div>

          {reduction.metadata && (
            <div style={{ marginTop: "15px", fontSize: "14px", color: "#666" }}>
              {reduction.metadata.loop_closures && (
                <div>Loop closures: {reduction.metadata.loop_closures}</div>
              )}
              {reduction.metadata.max_error && (
                <div>Max error: {reduction.metadata.max_error.toFixed(3)} ft</div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Plot Display */}
      {plotUrl && (
        <div style={styles.section}>
          <h3>Survey Plot</h3>
          <div style={styles.plotContainer}>
            <img src={plotUrl} alt="Survey Plot" style={styles.plotImage} />
          </div>
        </div>
      )}

      {/* Export Section */}
      <div style={styles.section}>
        <h3>Export Survey Data</h3>
        <p style={{ fontSize: "14px", color: "#666", marginBottom: "15px" }}>
          Download your survey data in various formats for use with other cave survey software.
        </p>

        <div style={styles.exportButtons}>
          <button
            style={styles.exportButton}
            onClick={() => handleExport("srv")}
            title="Walls format - popular in the US"
          >
            📄 .SRV (Walls)
          </button>

          <button
            style={styles.exportButton}
            onClick={() => handleExport("dat")}
            title="Compass format"
          >
            📄 .DAT (Compass)
          </button>

          <button
            style={styles.exportButton}
            onClick={() => handleExport("svx")}
            title="Survex format - open source"
          >
            📄 .SVX (Survex)
          </button>

          <button
            style={styles.exportButton}
            onClick={() => handleExport("th")}
            title="Therion format - for cave mapping"
          >
            📄 .TH (Therion)
          </button>

          <button
            style={styles.exportButton}
            onClick={() => handleExport("csv")}
            title="Simple CSV spreadsheet"
          >
            📊 .CSV
          </button>

          <button
            style={styles.exportButton}
            onClick={() => handleExport("json")}
            title="JSON data format"
          >
            {} .JSON
          </button>
        </div>

        {exportStatus && (
          <div style={{
            ...styles.statusMessage,
            color: exportStatus.startsWith("✓") ? "#28a745" :
                   exportStatus.startsWith("✗") ? "#dc3545" : "#0066cc"
          }}>
            {exportStatus}
          </div>
        )}
      </div>

      {/* Raw Data Section (collapsed by default) */}
      {surveyData && (
        <details style={styles.section}>
          <summary style={{ cursor: "pointer", fontWeight: "bold", marginBottom: "10px" }}>
            📋 View Raw Shot Data ({surveyData.total_shots} shots)
          </summary>
          <div style={styles.dataTable}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>#</th>
                  <th style={styles.th}>From</th>
                  <th style={styles.th}>To</th>
                  <th style={styles.th}>Distance</th>
                  <th style={styles.th}>Compass</th>
                  <th style={styles.th}>Clino</th>
                  <th style={styles.th}>Type</th>
                  <th style={styles.th}>Source</th>
                </tr>
              </thead>
              <tbody>
                {surveyData.shots.slice(0, 100).map((shot, idx) => (
                  <tr key={idx}>
                    <td style={styles.td}>{idx + 1}</td>
                    <td style={styles.td}>{shot.from}</td>
                    <td style={styles.td}>{shot.to || "-"}</td>
                    <td style={styles.td}>{shot.distance?.toFixed(2)}</td>
                    <td style={styles.td}>{shot.compass?.toFixed(1)}°</td>
                    <td style={styles.td}>{shot.clino?.toFixed(1)}°</td>
                    <td style={styles.td}>{shot.type}</td>
                    <td style={styles.td} title={shot.source_filename}>
                      {shot.source_filename?.substring(0, 15)}...
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {surveyData.shots.length > 100 && (
              <p style={{ textAlign: "center", color: "#666", marginTop: "10px" }}>
                Showing first 100 of {surveyData.shots.length} shots
              </p>
            )}
          </div>
        </details>
      )}
    </div>
  );
}

const styles = {
  container: {
    padding: "20px",
    maxWidth: "1200px",
    margin: "0 auto",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: "30px",
    paddingBottom: "20px",
    borderBottom: "2px solid #ddd",
  },
  closeButton: {
    padding: "8px 16px",
    backgroundColor: "#666",
    color: "white",
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
    fontSize: "14px",
  },
  error: {
    padding: "10px",
    marginBottom: "15px",
    backgroundColor: "#fee",
    border: "1px solid #fcc",
    borderRadius: "4px",
    color: "#c00",
  },
  section: {
    marginBottom: "30px",
    padding: "20px",
    backgroundColor: "#f9f9f9",
    borderRadius: "8px",
  },
  actionButtons: {
    display: "flex",
    gap: "15px",
    marginTop: "15px",
  },
  primaryButton: {
    padding: "12px 24px",
    backgroundColor: "#0066cc",
    color: "white",
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
    fontSize: "16px",
    fontWeight: "bold",
  },
  stats: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
    gap: "15px",
    marginTop: "15px",
  },
  statBox: {
    textAlign: "center",
    padding: "15px",
    backgroundColor: "white",
    borderRadius: "8px",
    boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
  },
  statValue: {
    fontSize: "32px",
    fontWeight: "bold",
    color: "#0066cc",
  },
  statLabel: {
    fontSize: "14px",
    color: "#666",
    marginTop: "5px",
  },
  plotContainer: {
    marginTop: "15px",
    backgroundColor: "white",
    padding: "20px",
    borderRadius: "8px",
    textAlign: "center",
  },
  plotImage: {
    maxWidth: "100%",
    height: "auto",
    border: "1px solid #ddd",
  },
  exportButtons: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))",
    gap: "10px",
  },
  exportButton: {
    padding: "10px 15px",
    backgroundColor: "white",
    color: "#0066cc",
    border: "2px solid #0066cc",
    borderRadius: "4px",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: "bold",
    transition: "all 0.2s",
  },
  statusMessage: {
    marginTop: "15px",
    padding: "10px",
    textAlign: "center",
    fontWeight: "bold",
    borderRadius: "4px",
    backgroundColor: "#f0f0f0",
  },
  dataTable: {
    overflowX: "auto",
    marginTop: "15px",
    backgroundColor: "white",
    borderRadius: "4px",
    padding: "15px",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: "13px",
  },
  th: {
    padding: "10px",
    backgroundColor: "#f4f4f4",
    borderBottom: "2px solid #ddd",
    textAlign: "left",
    fontWeight: "bold",
  },
  td: {
    padding: "8px",
    borderBottom: "1px solid #eee",
  },
  button: {
    padding: "10px 20px",
    backgroundColor: "#0066cc",
    color: "white",
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
    fontSize: "14px",
  },
};
