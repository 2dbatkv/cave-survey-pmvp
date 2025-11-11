import { useState } from "react";
import { uploadCSVDraft, pasteDraft, uploadImageDrafts } from "../api";

export default function DraftUpload({ surveyId, onDraftCreated }) {
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [pasteText, setPasteText] = useState("");
  const [showPaste, setShowPaste] = useState(false);
  const [imagePreviews, setImagePreviews] = useState([]);
  const [selectedImages, setSelectedImages] = useState([]);

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

  // Handle image selection (with preview)
  const handleImageSelection = (e) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;

    setUploadError(null);
    setSelectedImages(files);

    // Create preview URLs
    const previews = files.map(file => ({
      name: file.name,
      url: URL.createObjectURL(file)
    }));
    setImagePreviews(previews);
  };

  // Handle image upload and OCR processing
  const handleImageUpload = async () => {
    if (selectedImages.length === 0) {
      setUploadError("No images selected");
      return;
    }

    setUploading(true);
    setUploadError(null);

    try {
      const result = await uploadImageDrafts(surveyId, selectedImages);

      if (result.success) {
        // Clean up previews
        imagePreviews.forEach(preview => URL.revokeObjectURL(preview.url));
        setImagePreviews([]);
        setSelectedImages([]);
        onDraftCreated(result);
      } else {
        setUploadError("Upload failed");
      }
    } catch (err) {
      setUploadError(err.message || "Failed to process images");
    } finally {
      setUploading(false);
    }
  };

  // Cancel image selection
  const cancelImageSelection = () => {
    imagePreviews.forEach(preview => URL.revokeObjectURL(preview.url));
    setImagePreviews([]);
    setSelectedImages([]);
    setUploadError(null);
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
          <p>Scanned survey notes with OCR</p>
          <label htmlFor="image-upload" style={styles.button}>
            {uploading ? "Processing..." : "Choose Images"}
          </label>
          <input
            id="image-upload"
            type="file"
            accept="image/*"
            multiple
            onChange={handleImageSelection}
            disabled={uploading}
            style={{ display: "none" }}
          />
          {selectedImages.length > 0 && (
            <p style={{ marginTop: "10px", fontSize: "12px", color: "#666" }}>
              {selectedImages.length} image{selectedImages.length > 1 ? 's' : ''} selected
            </p>
          )}
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

      {/* Image Preview and Upload Section */}
      {imagePreviews.length > 0 && (
        <div style={styles.imagePreviewSection}>
          <h3>Selected Images for OCR Processing</h3>
          <p style={{ fontSize: "14px", color: "#666", marginBottom: "15px" }}>
            These images will be processed using OCR to extract survey data. Review the images and click "Process Images" when ready.
          </p>

          <div style={styles.previewGrid}>
            {imagePreviews.map((preview, idx) => (
              <div key={idx} style={styles.previewCard}>
                <img
                  src={preview.url}
                  alt={preview.name}
                  style={styles.previewImage}
                />
                <p style={styles.previewFileName}>{preview.name}</p>
              </div>
            ))}
          </div>

          <div style={styles.actionButtons}>
            <button
              style={styles.button}
              onClick={handleImageUpload}
              disabled={uploading}
            >
              {uploading ? "Processing with OCR..." : `📷 Process ${imagePreviews.length} Image${imagePreviews.length > 1 ? 's' : ''}`}
            </button>
            <button
              style={{...styles.button, backgroundColor: "#666", marginLeft: "10px"}}
              onClick={cancelImageSelection}
              disabled={uploading}
            >
              Cancel
            </button>
          </div>

          {uploading && (
            <div style={styles.processingMessage}>
              <p>🔄 Running OCR to extract survey data from images...</p>
              <p style={{ fontSize: "12px", color: "#666" }}>This may take a few moments depending on image quality and size.</p>
            </div>
          )}
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
  imagePreviewSection: {
    marginTop: "30px",
    padding: "20px",
    border: "2px solid #0066cc",
    borderRadius: "8px",
    backgroundColor: "#f0f8ff",
  },
  previewGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
    gap: "15px",
    marginBottom: "20px",
  },
  previewCard: {
    backgroundColor: "white",
    border: "1px solid #ddd",
    borderRadius: "8px",
    padding: "10px",
    textAlign: "center",
    boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
  },
  previewImage: {
    width: "100%",
    height: "150px",
    objectFit: "contain",
    borderRadius: "4px",
    marginBottom: "8px",
    backgroundColor: "#f5f5f5",
  },
  previewFileName: {
    fontSize: "12px",
    color: "#666",
    margin: "5px 0 0 0",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  actionButtons: {
    display: "flex",
    justifyContent: "center",
    marginTop: "15px",
  },
  processingMessage: {
    marginTop: "20px",
    padding: "15px",
    backgroundColor: "#fff3cd",
    border: "1px solid #ffc107",
    borderRadius: "4px",
    textAlign: "center",
  },
};
