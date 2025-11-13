import { useState, useEffect, useRef } from "react";
import { getDraft, updateDraft, commitDraft, parseText, parseConversation } from "../api";

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

  // New: Conversational parsing
  const [conversation, setConversation] = useState([]);
  const [userMessage, setUserMessage] = useState("");
  const [showConversation, setShowConversation] = useState(false);
  const [sendingMessage, setSendingMessage] = useState(false);
  const chatEndRef = useRef(null);

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

      // Load conversation history if exists
      if (data.draft_data?.conversation) {
        setConversation(data.draft_data.conversation);
      }

      setError(null);
    } catch (err) {
      setError(err.message || "Failed to load draft");
    } finally {
      setLoading(false);
    }
  };

  // NEW: Parse raw text into structured data (OLD METHOD - kept for compatibility)
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

  // NEW: Conversational parsing - send message to Claude
  const handleSendMessage = async () => {
    if (!userMessage.trim()) return;

    try {
      setSendingMessage(true);
      setError(null);

      const result = await parseConversation(surveyId, draftId, userMessage);

      // Update conversation with new messages
      setConversation(result.conversation || []);
      setShots(result.shots || []);
      setUserMessage(""); // Clear input

      // Show success message if template was learned
      if (result.template_learned) {
        setTimeout(() => {
          alert("✅ Template learned! Claude now understands your format and will apply it consistently.");
        }, 500);
      }

      // Scroll to bottom of chat
      setTimeout(() => {
        chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
      }, 100);

    } catch (err) {
      setError(err.message || "Failed to send message");
    } finally {
      setSendingMessage(false);
    }
  };

  // Start conversational parsing
  const handleStartConversation = () => {
    setShowConversation(true);
    setShowRawText(false);
    // Auto-send first message if no conversation exists
    if (conversation.length === 0) {
      setUserMessage("Please parse this cave survey data and ask me any clarifying questions.");
    }
  };

  // Auto-scroll chat to bottom when conversation updates
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation]);

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

      {/* NEW WORKFLOW: Raw Text Editor + Conversational Parsing */}
      {draft?.draft_data?.raw_text && (
        <div style={styles.toggleContainer}>
          <button
            style={showRawText && !showConversation ? styles.toggleButtonActive : styles.toggleButton}
            onClick={() => { setShowRawText(true); setShowConversation(false); }}
          >
            📝 Edit Raw Text
          </button>
          <button
            style={showConversation ? styles.toggleButtonActive : styles.toggleButton}
            onClick={handleStartConversation}
          >
            💬 Chat with Claude ({conversation.length / 2} messages)
          </button>
          <button
            style={!showRawText && !showConversation ? styles.toggleButtonActive : styles.toggleButton}
            onClick={() => { setShowRawText(false); setShowConversation(false); }}
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

      {/* CONVERSATIONAL PARSING MODE */}
      {showConversation && (
        <div style={styles.conversationContainer}>
          <div style={styles.conversationHeader}>
            <h3>💬 Chat with Claude to Parse Your Data</h3>
            <p>
              Have a conversation with Claude about how to parse your survey data.
              Claude can ask clarifying questions and refine the parsing based on your feedback.
            </p>
          </div>

          {/* Template Examples Helper */}
          {conversation.length === 0 && (
            <div style={styles.templateHelper}>
              <h4>💡 Pro Tip: Teach Claude Your Format</h4>
              <p>Claude will ask you to provide 1-3 example conversions showing:</p>
              <div style={styles.exampleBox}>
                <strong>Example 1 (Basic):</strong>
                <pre style={styles.examplePre}>
INPUT (from paper):  A1  A2  12.5ft  317°  -15°
OUTPUT (for software): A1 A2 12.5 317.0 -15.0
                </pre>
              </div>
              <div style={styles.exampleBox}>
                <strong>Example 2 (FS/BS Azimuth with LRUD):</strong>
                <pre style={styles.examplePre}>
INPUT:  B1  B2  15.2m  FS:278°  BS:98°  Inc:-12°  L:3.0  R:2.5  U:6.0  D:2.0
OUTPUT: B1 B2 15.2 278.0 98.0 -12.0 3.0 2.5 6.0 2.0
                </pre>
              </div>
              <p style={{ fontSize: "13px", color: "#666", marginTop: "10px" }}>
                This helps Claude learn your exact format needs: decimal places, spacing, column order, etc.
              </p>
            </div>
          )}

          {/* Chat Messages */}
          <div style={styles.chatMessages}>
            {conversation.length === 0 ? (
              <div style={styles.chatEmpty}>
                <p>👋 Start a conversation! Claude will help you parse the survey data and ask any clarifying questions.</p>
              </div>
            ) : (
              conversation.map((msg, index) => (
                <div
                  key={index}
                  style={msg.role === "user" ? styles.userMessage : styles.assistantMessage}
                >
                  <div style={styles.messageHeader}>
                    {msg.role === "user" ? "👤 You" : "🤖 Claude"}
                    {msg.shots_count !== undefined && (
                      <span style={styles.shotsBadge}>{msg.shots_count} shots</span>
                    )}
                  </div>
                  <div style={styles.messageContent}>
                    {msg.content}
                  </div>
                </div>
              ))
            )}
            <div ref={chatEndRef} />
          </div>

          {/* Input Area */}
          <div style={styles.chatInput}>
            <textarea
              value={userMessage}
              onChange={(e) => setUserMessage(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage();
                }
              }}
              style={styles.chatTextarea}
              placeholder="Ask Claude about the data format, clarify column meanings, or say 'commit' when ready..."
              rows={3}
              disabled={sendingMessage}
            />
            <button
              style={styles.sendButton}
              onClick={handleSendMessage}
              disabled={sendingMessage || !userMessage.trim()}
            >
              {sendingMessage ? "⏳ Sending..." : "Send 📤"}
            </button>
          </div>

          {/* Current Parsed Data Preview */}
          {shots.length > 0 && (
            <div style={styles.parsedPreview}>
              <h4>Current Parsed Data: {shots.length} shots</h4>
              <p style={{ fontSize: "13px", color: "#666" }}>
                Switch to "View Structured Data" tab to see full details and edit individual shots
              </p>
            </div>
          )}
        </div>
      )}

      {/* STRUCTURED DATA MODE */}
      {!showRawText && !showConversation && (
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

      {/* ACTIONS - Only show when in structured data view */}
      {!showRawText && !showConversation && (
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
  // Conversational parsing styles
  conversationContainer: {
    marginBottom: "20px",
    border: "2px solid #0066cc",
    borderRadius: "8px",
    padding: "20px",
    backgroundColor: "#f8f9fa",
  },
  conversationHeader: {
    marginBottom: "20px",
    paddingBottom: "15px",
    borderBottom: "2px solid #ddd",
  },
  chatMessages: {
    maxHeight: "500px",
    overflowY: "auto",
    marginBottom: "20px",
    padding: "10px",
    backgroundColor: "white",
    borderRadius: "6px",
    border: "1px solid #ddd",
  },
  chatEmpty: {
    padding: "40px 20px",
    textAlign: "center",
    color: "#666",
    fontSize: "14px",
  },
  userMessage: {
    marginBottom: "15px",
    padding: "12px",
    backgroundColor: "#e3f2fd",
    borderRadius: "8px",
    borderLeft: "4px solid #2196f3",
  },
  assistantMessage: {
    marginBottom: "15px",
    padding: "12px",
    backgroundColor: "#f1f8e9",
    borderRadius: "8px",
    borderLeft: "4px solid #8bc34a",
  },
  messageHeader: {
    fontWeight: "bold",
    marginBottom: "8px",
    fontSize: "13px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  shotsBadge: {
    fontSize: "11px",
    padding: "2px 8px",
    backgroundColor: "#4caf50",
    color: "white",
    borderRadius: "12px",
    fontWeight: "normal",
  },
  messageContent: {
    fontSize: "14px",
    lineHeight: "1.6",
    whiteSpace: "pre-wrap",
  },
  chatInput: {
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
  chatTextarea: {
    width: "100%",
    padding: "12px",
    border: "2px solid #ddd",
    borderRadius: "6px",
    fontSize: "14px",
    fontFamily: "inherit",
    resize: "vertical",
  },
  sendButton: {
    alignSelf: "flex-end",
    padding: "12px 30px",
    backgroundColor: "#0066cc",
    color: "white",
    border: "none",
    borderRadius: "6px",
    cursor: "pointer",
    fontSize: "15px",
    fontWeight: "bold",
  },
  parsedPreview: {
    marginTop: "20px",
    padding: "15px",
    backgroundColor: "#fff3cd",
    border: "1px solid #ffc107",
    borderRadius: "6px",
  },
  // Template helper styles
  templateHelper: {
    marginBottom: "20px",
    padding: "20px",
    backgroundColor: "#e8f4f8",
    border: "2px solid #4fc3f7",
    borderRadius: "8px",
  },
  exampleBox: {
    marginTop: "15px",
    marginBottom: "15px",
    padding: "15px",
    backgroundColor: "white",
    border: "1px solid #ddd",
    borderRadius: "6px",
  },
  examplePre: {
    marginTop: "8px",
    padding: "10px",
    backgroundColor: "#f5f5f5",
    border: "1px solid #ccc",
    borderRadius: "4px",
    fontFamily: "Consolas, Monaco, 'Courier New', monospace",
    fontSize: "13px",
    lineHeight: "1.5",
    overflow: "auto",
  },
};
