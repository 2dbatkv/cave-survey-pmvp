import { useState, useEffect } from "react";
import { listDrafts, deleteDraft } from "../api";
import DraftUpload from "./DraftUpload";
import DraftEditor from "./DraftEditor";

export default function DraftManager({ surveyId = 1 }) {
  const [view, setView] = useState("list"); // 'list' | 'upload' | 'edit'
  const [drafts, setDrafts] = useState([]);
  const [selectedDraftId, setSelectedDraftId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (view === "list") {
      loadDrafts();
    }
  }, [view]);

  const loadDrafts = async () => {
    try {
      setLoading(true);
      const data = await listDrafts(surveyId);
      setDrafts(data.drafts || []);
      setError(null);
    } catch (err) {
      setError(err.message || "Failed to load drafts");
    } finally {
      setLoading(false);
    }
  };

  const handleDraftCreated = (result) => {
    // After creating a draft, open it for editing
    setSelectedDraftId(result.draft_id);
    setView("edit");
  };

  const handleEditDraft = (draftId) => {
    setSelectedDraftId(draftId);
    setView("edit");
  };

  const handleDeleteDraft = async (draftId) => {
    if (!confirm("Delete this draft?")) return;

    try {
      await deleteDraft(surveyId, draftId);
      loadDrafts();
    } catch (err) {
      alert("Failed to delete draft: " + err.message);
    }
  };

  const handleCommitted = () => {
    setView("list");
    loadDrafts();
  };

  // Render different views
  if (view === "upload") {
    return (
      <div>
        <button
          style={styles.backButton}
          onClick={() => setView("list")}
        >
          ← Back to Drafts
        </button>
        <DraftUpload
          surveyId={surveyId}
          onDraftCreated={handleDraftCreated}
        />
      </div>
    );
  }

  if (view === "edit" && selectedDraftId) {
    return (
      <DraftEditor
        surveyId={surveyId}
        draftId={selectedDraftId}
        onClose={() => setView("list")}
        onCommitted={handleCommitted}
      />
    );
  }

  // Default: List view
  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h2>Survey Data Drafts</h2>
        <button
          style={styles.primaryButton}
          onClick={() => setView("upload")}
        >
          ➕ Upload New Data
        </button>
      </div>

      {error && (
        <div style={styles.error}>
          {error}
        </div>
      )}

      {loading ? (
        <div>Loading drafts...</div>
      ) : drafts.length === 0 ? (
        <div style={styles.emptyState}>
          <h3>No drafts yet</h3>
          <p>Upload CSV files or paste survey data to get started</p>
          <button
            style={styles.primaryButton}
            onClick={() => setView("upload")}
          >
            Upload Survey Data
          </button>
        </div>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>ID</th>
              <th style={styles.th}>Source</th>
              <th style={styles.th}>Filename</th>
              <th style={styles.th}>Shots</th>
              <th style={styles.th}>Status</th>
              <th style={styles.th}>Errors</th>
              <th style={styles.th}>Created</th>
              <th style={styles.th}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {drafts.map((draft) => (
              <tr key={draft.id}>
                <td style={styles.td}>{draft.id}</td>
                <td style={styles.td}>
                  {draft.source_type === "csv" && "📄 CSV"}
                  {draft.source_type === "photo" && "📷 Photo"}
                  {draft.source_type === "paste" && "📋 Paste"}
                  {draft.source_type === "manual" && "✍️ Manual"}
                </td>
                <td style={styles.td}>{draft.filename}</td>
                <td style={styles.td}>{draft.shot_count}</td>
                <td style={styles.td}>
                  <span
                    style={{
                      ...styles.badge,
                      backgroundColor:
                        draft.status === "committed"
                          ? "#28a745"
                          : draft.status === "draft"
                          ? "#ffc107"
                          : "#6c757d",
                    }}
                  >
                    {draft.status}
                  </span>
                </td>
                <td style={styles.td}>
                  {draft.has_errors ? (
                    <span style={styles.errorBadge}>
                      ⚠️ {draft.error_count}
                    </span>
                  ) : (
                    <span style={{ color: "#28a745" }}>✓</span>
                  )}
                </td>
                <td style={styles.td}>
                  {new Date(draft.created_at).toLocaleDateString()}
                </td>
                <td style={styles.td}>
                  <button
                    style={styles.actionButton}
                    onClick={() => handleEditDraft(draft.id)}
                    disabled={draft.status === "committed"}
                  >
                    {draft.status === "committed" ? "View" : "Edit"}
                  </button>
                  {draft.status !== "committed" && (
                    <button
                      style={{ ...styles.actionButton, marginLeft: "5px" }}
                      onClick={() => handleDeleteDraft(draft.id)}
                    >
                      Delete
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
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
    alignItems: "center",
    marginBottom: "20px",
  },
  primaryButton: {
    padding: "10px 20px",
    backgroundColor: "#0066cc",
    color: "white",
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: "bold",
  },
  backButton: {
    padding: "8px 16px",
    marginBottom: "20px",
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
  emptyState: {
    textAlign: "center",
    padding: "60px 20px",
    backgroundColor: "#f9f9f9",
    borderRadius: "8px",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: "14px",
    backgroundColor: "white",
    boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
  },
  th: {
    padding: "12px",
    backgroundColor: "#f4f4f4",
    borderBottom: "2px solid #ddd",
    textAlign: "left",
    fontWeight: "bold",
  },
  td: {
    padding: "12px",
    borderBottom: "1px solid #eee",
  },
  badge: {
    padding: "4px 8px",
    borderRadius: "12px",
    color: "white",
    fontSize: "12px",
    fontWeight: "bold",
    textTransform: "uppercase",
  },
  errorBadge: {
    color: "#c00",
    fontWeight: "bold",
  },
  actionButton: {
    padding: "6px 12px",
    backgroundColor: "#0066cc",
    color: "white",
    border: "none",
    borderRadius: "3px",
    cursor: "pointer",
    fontSize: "12px",
  },
};
