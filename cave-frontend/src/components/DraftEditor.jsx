import { useState, useEffect } from "react";
import { getDraft, updateDraft, commitDraft, parseText } from "../api";

export default function DraftEditor({ surveyId, draftId, onClose, onCommitted }) {
  const [draft, setDraft] = useState(null);
  const [shots, setShots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [parsing, setParsing] = useState(false);
  const [error, setError] = useState(null);
  const [editingCell, setEditingCell] = useState(null); // {row, col}

  // New: Raw text editing
  const [rawText, setRawText] = useState("");
  const [showRawText, setShowRawText] = useState(false);

  // Load draft data
  useEffect(() => {
    loadDraft();
  }, [draftId]);

  const loadDraft = async () => {
    try {
      setLoading(true);
      const data = await getDraft(surveyId, draftId);
      setDraft(data);
      setShots(data.draft_data?.shots || []);

      // NEW WORKFLOW: Check if draft has raw text (needs parsing)
      if (data.draft_data?.raw_text) {
        setRawText(data.draft_data.raw_text);
        setShowRawText(true); // Start in raw text mode
      }

      setError(null);
    } catch (err) {
      setError(err.message || "Failed to load draft");
    } finally {
      setLoading(false);
    }
  };

  // NEW: Parse raw text into structured data
  const handleParse = async () => {
    try {
      setParsing(true);
      setError(null);
      const result = await parseText(surveyId, draftId, rawText);
      setShots(result.shots || []);
      setShowRawText(false); // Switch to structured view
      alert(`Parsed ${result.shot_count} shots!`);
      await loadDraft(); // Reload to get updated draft
    } catch (err) {
      setError(err.message || "Failed to parse text");
    } finally {
      setParsing(false);
    }
  };

  // Handle cell edit
  const handleCellChange = (rowIndex, field, value) => {
    const newShots = [...shots];
    newShots[rowIndex] = {
      ...newShots[rowIndex],
      [field]: field === "from" || field === "to" ? value : parseFloat(value) || 0,
      edited: true,
    };
    setShots(newShots);
  };

  // Save draft (without committing)
  const handleSave = async () => {
    try {
      setSaving(true);
      const updatedDraftData = {
        ...draft.draft_data,
        shots: shots,
      };
      const result = await updateDraft(surveyId, draftId, updatedDraftData);
      setError(null);
      alert("Draft saved successfully!");
    } catch (err) {
      setError(err.message || "Failed to save draft");
    } finally {
      setSaving(false);
    }
  };

  // Commit draft to survey
  const handleCommit = async () => {
    if (!confirm("Commit this draft to the survey? This cannot be undone.")) {
      return;
    }

    try {
      setCommitting(true);
      await handleSave(); // Save first
      const result = await commitDraft(surveyId, draftId);
      alert("Draft committed successfully!");
      onCommitted(result);
    } catch (err) {
      setError(err.message || "Failed to commit draft");
    } finally {
      setCommitting(false);
    }
  };

  // Add new row
  const handleAddRow = () => {
    setShots([
      ...shots,
      {
        id: shots.length + 1,
        from: "",
        to: "",
        distance: 0,
        compass: 0,
        clino: 0,
        type: "survey",
        edited: true,
        errors: [],
      },
    ]);
  };

  // Delete row
  const handleDeleteRow = (rowIndex) => {
    if (confirm("Delete this shot?")) {
      setShots(shots.filter((_, i) => i !== rowIndex));
    }
  };

  if (loading) {
    return <div style={styles.container}>Loading draft...</div>;
  }

  if (error && !draft) {
    return (
      <div style={styles.container}>
        <div style={styles.error}>Error: {error}</div>
        <button style={styles.button} onClick={onClose}>
          Back
        </button>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div>
          <h2>Edit Draft: {draft?.filename}</h2>
          <p>
            {shots.length} shots | Status: {draft?.status} |
            {draft?.has_errors && ` ⚠️ ${draft.error_count} errors`}
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

      {draft?.validation_issues && draft.validation_issues.length > 0 && (
        <div style={styles.warning}>
          <strong>Validation Issues:</strong>
          <ul>
            {draft.validation_issues.slice(0, 5).map((issue, i) => (
              <li key={i}>
                Shot {issue.shot_id}: {issue.message}
              </li>
            ))}
          </ul>
          {draft.validation_issues.length > 5 && (
            <p>...and {draft.validation_issues.length - 5} more issues</p>
          )}
        </div>
      )}

      {/* NEW WORKFLOW: Raw Text Editor */}
      {draft?.draft_data?.raw_text && (
        <div style={styles.toggleContainer}>
          <button
            style={showRawText ? styles.toggleButtonActive : styles.toggleButton}
            onClick={() => setShowRawText(true)}
          >
            📝 Edit Raw Text
          </button>
          <button
            style={!showRawText ? styles.toggleButtonActive : styles.toggleButton}
            onClick={() => setShowRawText(false)}
          >
            📊 View Structured Data ({shots.length} shots)
          </button>
        </div>
      )}

      {/* RAW TEXT MODE */}
      {showRawText && draft?.draft_data?.raw_text && (
        <div style={styles.rawTextContainer}>
          <div style={styles.rawTextHeader}>
            <h3>Raw OCR Text (Editable)</h3>
            <p>
              Edit the text below to fix any OCR errors, then click Parse to
              convert it into structured survey data.
            </p>
          </div>

          <textarea
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
            style={styles.rawTextArea}
            rows={25}
            placeholder="Paste or edit survey data here..."
          />

          <div style={styles.rawTextActions}>
            <button
              style={{ ...styles.button, backgroundColor: "#28a745", fontSize: "16px", padding: "12px 24px" }}
              onClick={handleParse}
              disabled={parsing || !rawText.trim()}
            >
              {parsing ? "⏳ Parsing..." : "🔄 Parse into Structured Data"}
            </button>

            <p style={{ margin: 0, color: "#666", fontSize: "13px" }}>
              Claude Sonnet 4.5 will intelligently parse your survey data
            </p>
          </div>
        </div>
      )}

      {/* STRUCTURED DATA MODE */}
      {!showRawText && (
        <div style={styles.tableContainer}>
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
              <th style={styles.th}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {shots.map((shot, rowIndex) => (
              <tr
                key={shot.id || rowIndex}
                style={shot.edited ? styles.editedRow : {}}
              >
                <td style={styles.td}>{rowIndex + 1}</td>
                <td style={styles.td}>
                  <input
                    type="text"
                    value={shot.from || ""}
                    onChange={(e) => handleCellChange(rowIndex, "from", e.target.value)}
                    style={styles.input}
                  />
                </td>
                <td style={styles.td}>
                  <input
                    type="text"
                    value={shot.to || ""}
                    onChange={(e) => handleCellChange(rowIndex, "to", e.target.value)}
                    style={styles.input}
                    placeholder="-"
                  />
                </td>
                <td style={styles.td}>
                  <input
                    type="number"
                    value={shot.distance || 0}
                    onChange={(e) => handleCellChange(rowIndex, "distance", e.target.value)}
                    style={styles.inputNumber}
                    step="0.01"
                  />
                </td>
                <td style={styles.td}>
                  <input
                    type="number"
                    value={shot.compass || 0}
                    onChange={(e) => handleCellChange(rowIndex, "compass", e.target.value)}
                    style={styles.inputNumber}
                    step="0.1"
                    min="0"
                    max="360"
                  />
                </td>
                <td style={styles.td}>
                  <input
                    type="number"
                    value={shot.clino || 0}
                    onChange={(e) => handleCellChange(rowIndex, "clino", e.target.value)}
                    style={styles.inputNumber}
                    step="0.1"
                    min="-90"
                    max="90"
                  />
                </td>
                <td style={styles.td}>
                  <select
                    value={shot.type || "survey"}
                    onChange={(e) => handleCellChange(rowIndex, "type", e.target.value)}
                    style={styles.select}
                  >
                    <option value="survey">Survey</option>
                    <option value="splay">Splay</option>
                  </select>
                </td>
                <td style={styles.td}>
                  <button
                    style={styles.deleteButton}
                    onClick={() => handleDeleteRow(rowIndex)}
                    title="Delete shot"
                  >
                    🗑️
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      )}

      {/* ACTIONS - Only show when not in raw text mode */}
      {!showRawText && (
      <div style={styles.actions}>
        <button style={styles.button} onClick={handleAddRow}>
          ➕ Add Row
        </button>

        <div style={styles.rightActions}>
          <button
            style={styles.button}
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? "Saving..." : "💾 Save Draft"}
          </button>

          <button
            style={{ ...styles.button, backgroundColor: "#28a745" }}
            onClick={handleCommit}
            disabled={committing || draft?.has_errors}
            title={draft?.has_errors ? "Fix validation errors before committing" : ""}
          >
            {committing ? "Committing..." : "✓ Commit to Survey"}
          </button>
        </div>
      </div>
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
    marginBottom: "20px",
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
  warning: {
    padding: "10px",
    marginBottom: "15px",
    backgroundColor: "#fff3cd",
    border: "1px solid #ffc107",
    borderRadius: "4px",
    color: "#856404",
  },
  tableContainer: {
    overflowX: "auto",
    marginBottom: "20px",
    border: "1px solid #ddd",
    borderRadius: "4px",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: "14px",
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
  editedRow: {
    backgroundColor: "#fffbcc",
  },
  input: {
    width: "100%",
    padding: "4px",
    border: "1px solid #ccc",
    borderRadius: "3px",
    fontSize: "13px",
  },
  inputNumber: {
    width: "80px",
    padding: "4px",
    border: "1px solid #ccc",
    borderRadius: "3px",
    fontSize: "13px",
  },
  select: {
    padding: "4px",
    border: "1px solid #ccc",
    borderRadius: "3px",
    fontSize: "13px",
  },
  deleteButton: {
    padding: "4px 8px",
    backgroundColor: "transparent",
    border: "none",
    cursor: "pointer",
    fontSize: "16px",
  },
  actions: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "10px",
  },
  rightActions: {
    display: "flex",
    gap: "10px",
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
  // NEW: Raw text editing styles
  toggleContainer: {
    display: "flex",
    gap: "10px",
    marginBottom: "20px",
    borderBottom: "2px solid #ddd",
    paddingBottom: "10px",
  },
  toggleButton: {
    padding: "10px 20px",
    backgroundColor: "#f4f4f4",
    color: "#333",
    border: "1px solid #ddd",
    borderRadius: "4px 4px 0 0",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: "500",
  },
  toggleButtonActive: {
    padding: "10px 20px",
    backgroundColor: "#0066cc",
    color: "white",
    border: "1px solid #0066cc",
    borderRadius: "4px 4px 0 0",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: "bold",
  },
  rawTextContainer: {
    marginBottom: "20px",
  },
  rawTextHeader: {
    marginBottom: "15px",
  },
  rawTextArea: {
    width: "100%",
    padding: "12px",
    border: "2px solid #ddd",
    borderRadius: "4px",
    fontSize: "14px",
    fontFamily: "Consolas, Monaco, 'Courier New', monospace",
    lineHeight: "1.5",
    resize: "vertical",
    minHeight: "400px",
  },
  rawTextActions: {
    marginTop: "15px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "10px",
  },
};
