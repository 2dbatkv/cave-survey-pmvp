const API = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/,"");

// Helper function to get auth headers
function getAuthHeaders() {
  const token = localStorage.getItem("auth_token");
  const headers = { "Content-Type": "application/json" };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

export async function health() {
  const r = await fetch(`${API}/`);
  if (!r.ok) throw new Error("health failed");
  return r.json();
}

export async function reduceTraverse(payload) {
  const r = await fetch(`${API}/reduce`, {
    method: "POST", headers: { "Content-Type":"application/json" },
    body: JSON.stringify(payload)
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function plotTraverse(payload) {
  const r = await fetch(`${API}/plot`, {
    method: "POST", headers: { "Content-Type":"application/json" },
    body: JSON.stringify(payload)
  });
  if (!r.ok) throw new Error(await r.text());
  const blob = await r.blob();
  return URL.createObjectURL(blob);   // image URL for <img src=...>
}

export async function submitFeedback(feedbackText) {
  const r = await fetch(`${API}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      feedback_text: feedbackText,
      user_session: `session_${Date.now()}`,
      category: "user_idea"
    })
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

// ============================================================
// DRAFT MANAGEMENT APIs
// ============================================================

export async function uploadCSVDraft(surveyId, csvContent, filename) {
  const r = await fetch(`${API}/surveys/${surveyId}/drafts/upload-csv`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({
      csv_file: csvContent,
      filename: filename
    })
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function pasteDraft(surveyId, content, format = "topodroid") {
  const r = await fetch(`${API}/surveys/${surveyId}/drafts/paste-data`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({
      content: content,
      format: format
    })
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function listDrafts(surveyId) {
  const r = await fetch(`${API}/surveys/${surveyId}/drafts`, {
    headers: getAuthHeaders()
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getDraft(surveyId, draftId) {
  const r = await fetch(`${API}/surveys/${surveyId}/drafts/${draftId}`, {
    headers: getAuthHeaders()
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function updateDraft(surveyId, draftId, draftData) {
  const r = await fetch(`${API}/surveys/${surveyId}/drafts/${draftId}`, {
    method: "PUT",
    headers: getAuthHeaders(),
    body: JSON.stringify({ draft_data: draftData })
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function commitDraft(surveyId, draftId) {
  const r = await fetch(`${API}/surveys/${surveyId}/drafts/${draftId}/commit`, {
    method: "POST",
    headers: getAuthHeaders()
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function deleteDraft(surveyId, draftId) {
  const r = await fetch(`${API}/surveys/${surveyId}/drafts/${draftId}`, {
    method: "DELETE",
    headers: getAuthHeaders()
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

// ============================================================
// SURVEY PROCESSING & EXPORT APIs
// ============================================================

export async function getSurveyData(surveyId) {
  const r = await fetch(`${API}/surveys/${surveyId}/data`, {
    headers: getAuthHeaders()
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function reduceSurvey(surveyId) {
  const r = await fetch(`${API}/surveys/${surveyId}/reduce`, {
    method: "POST",
    headers: getAuthHeaders()
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function getSurveyPlot(surveyId) {
  const r = await fetch(`${API}/surveys/${surveyId}/plot`, {
    method: "POST",
    headers: getAuthHeaders()
  });
  if (!r.ok) throw new Error(await r.text());
  const blob = await r.blob();
  return URL.createObjectURL(blob);
}

export async function exportSurvey(surveyId, format) {
  const r = await fetch(`${API}/surveys/${surveyId}/export/${format}`, {
    headers: getAuthHeaders()
  });
  if (!r.ok) throw new Error(await r.text());
  
  // Get filename from Content-Disposition header
  const contentDisposition = r.headers.get('Content-Disposition');
  const filenameMatch = contentDisposition && contentDisposition.match(/filename=(.+)/);
  const filename = filenameMatch ? filenameMatch[1] : `survey_${surveyId}.${format}`;
  
  // Download the file
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  
  return { success: true, filename };
}
