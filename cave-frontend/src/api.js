const API = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/,"");

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
