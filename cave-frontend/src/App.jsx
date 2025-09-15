// src/App.jsx
import { useMemo, useState } from "react";
import { health, reduceTraverse, plotTraverse, submitFeedback } from "./api";

const AZ_MIN = 0;
const AZ_MAX = 360;  // open upper bound in normalize, but UI shows 0..360
const INC_MIN = -90;
const INC_MAX = 90;

function normalizeAzimuth(v) {
  if (Number.isNaN(v)) return 0;
  // map to [0, 360)
  const m = ((v % 360) + 360) % 360;
  return m;
}

function clampInclination(v) {
  if (Number.isNaN(v)) return 0;
  return Math.max(INC_MIN, Math.min(INC_MAX, v));
}

function toNum(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n : 0;
}

function validateShot(s) {
  const errs = [];
  if (!s.from_station?.trim()) errs.push("From station required");
  if (!s.to_station?.trim()) errs.push("To station required");
  if (!(s.slope_distance > 0)) errs.push("Distance must be > 0");
  if (!(s.azimuth_deg >= 0 && s.azimuth_deg <= 360)) errs.push("Azimuth must be 0–360");
  if (!(s.inclination_deg >= -90 && s.inclination_deg <= 90)) errs.push("Inclination must be -90–90");
  return errs;
}

export default function App() {
  const [shots, setShots] = useState([
    { from_station: "S0", to_station: "S1", slope_distance: 12.5, azimuth_deg: 90, inclination_deg: 0 },
  ]);
  const [meta, setMeta] = useState(null);
  const [plotUrl, setPlotUrl] = useState(null);
  const [status, setStatus] = useState("");
  const [feedbackText, setFeedbackText] = useState("");
  const [feedbackStatus, setFeedbackStatus] = useState("");
  
  // Paste functionality state
  const [pasteText, setPasteText] = useState("");
  const [pasteMode, setPasteMode] = useState(false);
  const [parseErrors, setParseErrors] = useState([]);
  const [previewShots, setPreviewShots] = useState([]);

  const apiBase = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
  const payload = { origin_x: 0, origin_y: 0, origin_z: 0, section: "demo", shots };

  // compute validation for all shots
  const rowErrors = useMemo(() => shots.map(validateShot), [shots]);
  const hasErrors = rowErrors.some((errs) => errs.length > 0);

  function updateShot(i, patch) {
    setShots((prev) => {
      const next = [...prev];
      next[i] = { ...next[i], ...patch };
      return next;
    });
  }

  function addShot() {
    const n = shots.length;
    setShots([
      ...shots,
      { from_station: `S${n}`, to_station: `S${n + 1}`, slope_distance: 10, azimuth_deg: 0, inclination_deg: 0 },
    ]);
  }

  // Paste functionality functions
  function parseTextData(text) {
    const lines = text.trim().split('\n');
    const parsed = [];
    const errors = [];
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      
      // Skip empty lines and comments
      if (!line || line.startsWith('#') || line.startsWith(';') || line.startsWith('//')) {
        continue;
      }
      
      try {
        const shot = parseLine(line, i + 1);
        if (shot) {
          const validationErrors = validateShot(shot);
          if (validationErrors.length === 0) {
            parsed.push(shot);
          } else {
            errors.push(`Line ${i + 1}: ${validationErrors.join(', ')}`);
          }
        }
      } catch (error) {
        errors.push(`Line ${i + 1}: Invalid format - ${error.message}`);
      }
    }
    
    return { shots: parsed, errors };
  }

  function parseLine(line, lineNumber) {
    // Try JSON format first
    if (line.startsWith('{')) {
      try {
        return JSON.parse(line);
      } catch (e) {
        throw new Error('Invalid JSON format');
      }
    }
    
    // Parse space/tab/comma separated values
    const parts = line.split(/[\s,]+/).filter(part => part.trim() !== '');
    
    if (parts.length < 5) {
      throw new Error('Expected 5 values: from_station to_station distance azimuth inclination');
    }
    
    const [from_station, to_station, distance, azimuth, inclination] = parts;
    
    return {
      from_station: from_station.trim(),
      to_station: to_station.trim(),
      slope_distance: toNum(distance),
      azimuth_deg: normalizeAzimuth(toNum(azimuth.replace(/[°'"].*/, ''))), // Remove degree symbols
      inclination_deg: clampInclination(toNum(inclination.replace(/[°'"].*/, '')))
    };
  }

  function handlePasteTextChange(e) {
    const text = e.target.value;
    setPasteText(text);
    
    if (text.trim()) {
      const result = parseTextData(text);
      setPreviewShots(result.shots);
      setParseErrors(result.errors);
    } else {
      setPreviewShots([]);
      setParseErrors([]);
    }
  }

  function addParsedShots(replaceAll = false) {
    if (replaceAll) {
      setShots(previewShots);
    } else {
      setShots(prev => [...prev, ...previewShots]);
    }
    
    // Clear paste area
    setPasteText("");
    setPreviewShots([]);
    setParseErrors([]);
    setPasteMode(false);
    
    setStatus(`Added ${previewShots.length} shots from pasted data`);
  }

  function clearPasteData() {
    setPasteText("");
    setPreviewShots([]);
    setParseErrors([]);
  }

  async function onHealth() {
    try {
      const res = await health();
      setStatus(JSON.stringify(res));
    } catch (e) {
      setStatus(`Health error: ${e}`);
    }
  }

  async function onReduce() {
    if (hasErrors) return;
    setMeta(null);
    setPlotUrl(null);
    setStatus("Reducing…");
    try {
      const res = await reduceTraverse(payload);
      setMeta(res.meta || res);
      setStatus("Reduced ✅");
    } catch (e) {
      setStatus(`Reduce error: ${e}`);
    }
  }

  async function onPlot() {
    if (hasErrors) return;
    setStatus("Plotting…");
    try {
      const url = await plotTraverse(payload);
      setPlotUrl(url);
      setStatus("Plotted ✅");
    } catch (e) {
      setStatus(`Plot error: ${e}`);
    }
  }

  async function onSubmitFeedback() {
    if (!feedbackText.trim()) {
      setFeedbackStatus("Please enter some feedback");
      return;
    }
    
    setFeedbackStatus("Submitting...");
    try {
      const result = await submitFeedback(feedbackText.trim());
      setFeedbackStatus(result.message || "Thank you for your feedback!");
      setFeedbackText("");
    } catch (e) {
      setFeedbackStatus(`Error: ${e}`);
    }
  }

  const rowStyle = {
    display: "grid",
    gridTemplateColumns: "repeat(5, minmax(120px, 1fr))",
    gap: 8,
    alignItems: "center",
    marginBottom: 6,
  };

  return (
    <div style={{ padding: 24, fontFamily: "system-ui" }}>
      <h1 style={{ marginBottom: 8 }}>Cave Local Pre-MVP</h1>
      <p style={{ color: "#666", marginTop: 0, marginBottom: 16 }}>API: {apiBase}</p>

      {shots.map((s, i) => (
        <div key={i} style={{ marginBottom: 4 }}>
          <div style={rowStyle}>
            {/* From */}
            <input
              value={s.from_station}
              onChange={(e) => updateShot(i, { from_station: e.target.value })}
              placeholder="from"
            />
            {/* To */}
            <input
              value={s.to_station}
              onChange={(e) => updateShot(i, { to_station: e.target.value })}
              placeholder="to"
            />
            {/* Distance */}
            <input
              type="number"
              min={0.01}
              step="0.01"
              value={s.slope_distance}
              onChange={(e) => updateShot(i, { slope_distance: toNum(e.target.value) })}
              onBlur={(e) => {
                const v = Math.max(0.01, toNum(e.target.value));
                updateShot(i, { slope_distance: v });
              }}
              placeholder="distance"
              title="Slope distance (> 0)"
            />
            {/* Azimuth */}
            <input
              type="number"
              min={AZ_MIN}
              max={AZ_MAX}
              step="0.1"
              value={s.azimuth_deg}
              onChange={(e) => updateShot(i, { azimuth_deg: toNum(e.target.value) })}
              onBlur={(e) => {
                const v = normalizeAzimuth(toNum(e.target.value));
                updateShot(i, { azimuth_deg: v });
              }}
              placeholder="azimuth"
              title="Azimuth (0–360)"
            />
            {/* Inclination */}
            <input
              type="number"
              min={INC_MIN}
              max={INC_MAX}
              step="0.1"
              value={s.inclination_deg}
              onChange={(e) => updateShot(i, { inclination_deg: toNum(e.target.value) })}
              onBlur={(e) => {
                const v = clampInclination(toNum(e.target.value));
                updateShot(i, { inclination_deg: v });
              }}
              placeholder="inclination"
              title="Inclination (-90 to 90)"
            />
          </div>
          {/* Inline error messages */}
          {rowErrors[i].length > 0 && (
            <div style={{ color: "#b00020", fontSize: 12, marginTop: 2 }}>
              {rowErrors[i].join(" · ")}
            </div>
          )}
        </div>
      ))}

      {/* Paste Data Section */}
      <div style={{ marginTop: 20, marginBottom: 20, padding: 15, border: '1px solid #ddd', borderRadius: 6, backgroundColor: '#f9f9f9' }}>
        <div style={{ marginBottom: 10 }}>
          <button 
            onClick={() => setPasteMode(!pasteMode)}
            style={{ marginRight: 10, padding: '6px 12px', backgroundColor: '#007bff', color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 14 }}
          >
            {pasteMode ? 'Hide' : 'Paste Survey Data'}
          </button>
          <span style={{ fontSize: 14, color: '#666' }}>
            Bulk import cave survey data from text
          </span>
        </div>
        
        {pasteMode && (
          <div>
            <div style={{ marginBottom: 10 }}>
              <label style={{ display: 'block', marginBottom: 5, fontWeight: 600, fontSize: 14 }}>
                Paste cave survey data (multiple formats supported):
              </label>
              <textarea
                value={pasteText}
                onChange={handlePasteTextChange}
                placeholder={`Supported formats:

Space/tab separated:
S0 S1 2.5 90 0
S1 S2 10 0 0

Comma separated:
S0,S1,2.5,90,0
S1,S2,10,0,0

JSON format:
{"from_station": "S0", "to_station": "S1", "slope_distance": 2.5, "azimuth_deg": 90, "inclination_deg": 0}

Comments (lines starting with # ; //) are ignored`}
                style={{ 
                  width: '100%', 
                  height: 120, 
                  padding: 8, 
                  border: '1px solid #ccc', 
                  borderRadius: 4,
                  fontFamily: 'monospace',
                  fontSize: 12,
                  resize: 'vertical'
                }}
              />
            </div>
            
            {/* Parse Errors */}
            {parseErrors.length > 0 && (
              <div style={{ marginBottom: 10, padding: 8, backgroundColor: '#ffebee', border: '1px solid #ffcdd2', borderRadius: 4 }}>
                <strong style={{ color: '#c62828', fontSize: 14 }}>Parse Errors:</strong>
                <ul style={{ margin: '4px 0', paddingLeft: 16 }}>
                  {parseErrors.map((error, idx) => (
                    <li key={idx} style={{ color: '#c62828', fontSize: 13 }}>{error}</li>
                  ))}
                </ul>
              </div>
            )}
            
            {/* Preview Table */}
            {previewShots.length > 0 && (
              <div style={{ marginBottom: 10 }}>
                <strong style={{ color: '#2e7d32', fontSize: 14 }}>Preview ({previewShots.length} shots parsed):</strong>
                <div style={{ maxHeight: 120, overflowY: 'auto', border: '1px solid #ddd', borderRadius: 4, marginTop: 4 }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                    <thead style={{ backgroundColor: '#f5f5f5', position: 'sticky', top: 0 }}>
                      <tr>
                        <th style={{ padding: 4, border: '1px solid #ddd', textAlign: 'left' }}>From</th>
                        <th style={{ padding: 4, border: '1px solid #ddd', textAlign: 'left' }}>To</th>
                        <th style={{ padding: 4, border: '1px solid #ddd', textAlign: 'left' }}>Distance</th>
                        <th style={{ padding: 4, border: '1px solid #ddd', textAlign: 'left' }}>Azimuth</th>
                        <th style={{ padding: 4, border: '1px solid #ddd', textAlign: 'left' }}>Inclination</th>
                      </tr>
                    </thead>
                    <tbody>
                      {previewShots.map((shot, idx) => (
                        <tr key={idx}>
                          <td style={{ padding: 4, border: '1px solid #ddd' }}>{shot.from_station}</td>
                          <td style={{ padding: 4, border: '1px solid #ddd' }}>{shot.to_station}</td>
                          <td style={{ padding: 4, border: '1px solid #ddd' }}>{shot.slope_distance}</td>
                          <td style={{ padding: 4, border: '1px solid #ddd' }}>{shot.azimuth_deg}°</td>
                          <td style={{ padding: 4, border: '1px solid #ddd' }}>{shot.inclination_deg}°</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
            
            {/* Action Buttons */}
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <button
                onClick={() => addParsedShots(false)}
                disabled={previewShots.length === 0}
                style={{ 
                  padding: '6px 12px', 
                  backgroundColor: previewShots.length > 0 ? '#28a745' : '#ccc', 
                  color: 'white', 
                  border: 'none', 
                  borderRadius: 4, 
                  cursor: previewShots.length > 0 ? 'pointer' : 'not-allowed',
                  fontSize: 13
                }}
              >
                Add to Existing ({previewShots.length})
              </button>
              
              <button
                onClick={() => addParsedShots(true)}
                disabled={previewShots.length === 0}
                style={{ 
                  padding: '6px 12px', 
                  backgroundColor: previewShots.length > 0 ? '#dc3545' : '#ccc', 
                  color: 'white', 
                  border: 'none', 
                  borderRadius: 4, 
                  cursor: previewShots.length > 0 ? 'pointer' : 'not-allowed',
                  fontSize: 13
                }}
              >
                Replace All
              </button>
              
              <button
                onClick={clearPasteData}
                style={{ 
                  padding: '6px 12px', 
                  backgroundColor: '#6c757d', 
                  color: 'white', 
                  border: 'none', 
                  borderRadius: 4, 
                  cursor: 'pointer',
                  fontSize: 13
                }}
              >
                Clear
              </button>
            </div>
          </div>
        )}
      </div>

      <div style={{ marginTop: 8, marginBottom: 16 }}>
        <button onClick={addShot}>+ Add shot</button>
      </div>

      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <button onClick={onHealth}>Test backend</button>
        <button onClick={onReduce} disabled={hasErrors} title={hasErrors ? "Fix row errors first" : ""}>
          Reduce
        </button>
        <button onClick={onPlot} disabled={hasErrors} title={hasErrors ? "Fix row errors first" : ""}>
          Plot
        </button>
        {hasErrors && <span style={{ color: "#b00020", fontSize: 13 }}>Fix errors before running.</span>}
      </div>

      {status && <p style={{ marginTop: 12 }}>{status}</p>}

      {meta && (
        <pre style={{ background: "#f6f6f6", padding: 12, borderRadius: 6, overflowX: "auto" }}>
          {JSON.stringify(meta, null, 2)}
        </pre>
      )}

      {plotUrl && (
        <div style={{ marginTop: 12 }}>
          <img src={plotUrl} alt="Cave plot" style={{ maxWidth: 700, border: "1px solid #ddd" }} />
        </div>
      )}

      <div style={{ marginTop: 32, padding: 16, background: "#f9f9f9", borderRadius: 8 }}>
        <h3 style={{ marginTop: 0, marginBottom: 12, color: "#333" }}>Submit an Idea 💡</h3>
        <p style={{ margin: "0 0 12px 0", fontSize: 14, color: "#666" }}>
          Help improve CaveMapper! Share your ideas, suggestions, or feedback.
        </p>
        <textarea
          value={feedbackText}
          onChange={(e) => setFeedbackText(e.target.value)}
          placeholder="What would you like to see in CaveMapper? Any bugs, features, or improvements you'd suggest?"
          style={{
            width: "100%",
            minHeight: 80,
            padding: 8,
            border: "1px solid #ccc",
            borderRadius: 4,
            fontFamily: "system-ui",
            fontSize: 14,
            resize: "vertical"
          }}
        />
        <div style={{ marginTop: 8, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <button
            onClick={onSubmitFeedback}
            disabled={!feedbackText.trim()}
            style={{
              padding: "8px 16px",
              background: feedbackText.trim() ? "#007bff" : "#ccc",
              color: "white",
              border: "none",
              borderRadius: 4,
              cursor: feedbackText.trim() ? "pointer" : "not-allowed",
              fontWeight: 500
            }}
          >
            Submit Idea
          </button>
          {feedbackStatus && (
            <span style={{ 
              fontSize: 14, 
              color: feedbackStatus.includes("Error") ? "#b00020" : "#28a745" 
            }}>
              {feedbackStatus}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
