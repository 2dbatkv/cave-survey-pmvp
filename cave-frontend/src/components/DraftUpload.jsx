import { useState } from "react";
import { uploadCSVDraft, pasteDraft } from "../api";

export default function DraftUpload({ surveyId, onDraftCreated }) {
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [pasteText, setPasteText] = useState("");
  const [showPaste, setShowPaste] = useState(false);

  // Handle CSV file upload
  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadError(null);

    try {
      const text = await file.text();
      const result = await uploadCSVDraft(surveyId, text, file.name);

      if (result.success) {
        onDraftCreated(result);
      } else {
        setUploadError("Upload failed");
      }
    } catch (err) {
      setUploadError(err.message || "Failed to upload file");
    } finally {
      setUploading(false);
      e.target.value = ""; // Reset file input
    }
  };

  // Handle image upload (photos of survey notes)
  const handleImageUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadError(null);

    try {
      // TODO: Implement image upload + OCR
      setUploadError("Image/OCR feature coming soon!");
    } catch (err) {
      setUploadError(err.message || "Failed to upload image");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  // Handle paste data
  const handlePaste = async () => {
    if (!pasteText.trim()) {
      setUploadError("No data to paste");
      return;
    }

    setUploading(true);
    setUploadError(null);

    try {
      const result = await pasteDraft(surveyId, pasteText, "topodroid");

      if (result.success) {
        setPasteText("");
        setShowPaste(false);
        onDraftCreated(result);
      } else {
        setUploadError("Paste failed");
      }
    } catch (err) {
      setUploadError(err.message || "Failed to paste data");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div style={styles.container}>
      <h2>Upload Survey Data</h2>

      {uploadError && (
        <div style={styles.error}>
          ⚠️ {uploadError}
        </div>
      )}

      <div style={styles.uploadOptions}>
        {/* CSV Upload */}
        <div style={styles.uploadBox}>
          <h3>📄 Upload CSV File</h3>
          <p>TopoDroid CSV format</p>
          <label htmlFor="csv-upload" style={styles.button}>
            {uploading ? "Uploading..." : "Choose CSV File"}
          </label>
          <input
            id="csv-upload"
            type="file"
            accept=".csv"
            onChange={handleFileUpload}
            disabled={uploading}
            style={{ display: "none" }}
          />
        </div>

        {/* Image Upload */}
        <div style={styles.uploadBox}>
          <h3>📷 Upload Photos</h3>
          <p>Scanned survey notes (coming soon)</p>
          <label htmlFor="image-upload" style={{...styles.button, opacity: 0.5}}>
            Choose Image
          </label>
          <input
            id="image-upload"
            type="file"
            accept="image/*"
            onChange={handleImageUpload}
            disabled={true}
            style={{ display: "none" }}
          />
        </div>

        {/* Paste Data */}
        <div style={styles.uploadBox}>
          <h3>📋 Paste Data</h3>
          <p>Copy/paste survey data directly</p>
          <button
            style={styles.button}
            onClick={() => setShowPaste(!showPaste)}
          >
            {showPaste ? "Cancel" : "Paste Data"}
          </button>
        </div>
      </div>

      {/* Paste Text Area */}
      {showPaste && (
        <div style={styles.pasteArea}>
          <textarea
            style={styles.textarea}
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
            placeholder="Paste TopoDroid CSV data here..."
            rows={10}
          />
          <button
            style={styles.button}
            onClick={handlePaste}
            disabled={uploading || !pasteText.trim()}
          >
            {uploading ? "Processing..." : "Upload Pasted Data"}
          </button>
        </div>
      )}
    </div>
  );
}

const styles = {
  container: {
    padding: "20px",
    maxWidth: "900px",
    margin: "0 auto",
  },
  error: {
    padding: "10px",
    marginBottom: "15px",
    backgroundColor: "#fee",
    border: "1px solid #fcc",
    borderRadius: "4px",
    color: "#c00",
  },
  uploadOptions: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
    gap: "20px",
    marginTop: "20px",
  },
  uploadBox: {
    padding: "20px",
    border: "2px dashed #ccc",
    borderRadius: "8px",
    textAlign: "center",
  },
  button: {
    display: "inline-block",
    padding: "10px 20px",
    backgroundColor: "#0066cc",
    color: "white",
    border: "none",
    borderRadius: "4px",
    cursor: "pointer",
    fontSize: "14px",
    textDecoration: "none",
  },
  pasteArea: {
    marginTop: "20px",
    padding: "20px",
    border: "1px solid #ddd",
    borderRadius: "8px",
    backgroundColor: "#f9f9f9",
  },
  textarea: {
    width: "100%",
    padding: "10px",
    fontFamily: "monospace",
    fontSize: "12px",
    border: "1px solid #ccc",
    borderRadius: "4px",
    marginBottom: "10px",
  },
};
