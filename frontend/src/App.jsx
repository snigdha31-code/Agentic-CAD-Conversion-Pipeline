import { useEffect, useMemo, useState } from "react";
 // Base URL for the backend API
const API = "http://127.0.0.1:8000";

// Main App component for the Agentic CAD Converter
export default function App() {
  const [file, setFile] = useState(null);
  const [outputType, setOutputType] = useState("pdf");
  const [jobId, setJobId] = useState("");
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);

  // useMemo to compute download URL only when jobId changes
  const downloadUrl = useMemo(() => {
    if (!jobId) return "";
    return `${API}/jobs/${jobId}/download`;
  }, [jobId]);

  // Function to create a new job by uploading the file and selected output type
  async function createJob() {
    setError("");
    setJob(null);

    if (!file) {
      setError("Please select a .dxf or .dwg file.");
      return;
    }

    const form = new FormData();
    form.append("file", file);
    form.append("output_type", outputType);

    setUploading(true);

    // Make a POST request to the backend to create a new job
    try {
      const res = await fetch(`${API}/jobs`, { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Upload failed");
      setJobId(data.job_id);
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setUploading(false);
    }
  }
  // Function to fetch the status of the job using its ID
  async function fetchStatus(id) {
    const res = await fetch(`${API}/jobs/${id}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data?.detail || "Status failed");
    return data;
  }
  // useEffect to poll the job status every 1.5 seconds until it's complete or failed
  useEffect(() => {
    if (!jobId) return;

    let timer = null;
    let stopped = false;

    async function poll() {
      try {
        const data = await fetchStatus(jobId);
        setJob(data);

        if (data.status === "complete" || data.status === "failed") {
          stopped = true;
          return;
        }
      } catch (e) {
        setError(e.message || String(e));
        stopped = true;
      }

      if (!stopped) timer = setTimeout(poll, 1500);
    }
    // Start polling the job status
    poll();
    return () => timer && clearTimeout(timer);
  }, [jobId]);

  return (
    <div style={{ fontFamily: "system-ui", maxWidth: 820, margin: "40px auto", padding: 16 }}>
      <h1 style={{ marginBottom: 6 }}>Agentic CAD Converter</h1>
      <p style={{ marginTop: 0, color: "#444" }}>
        Upload a DXF/DWG, choose output, track status, download result.
      </p>

      <div style={{ border: "1px solid #ddd", borderRadius: 12, padding: 16 }}>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          <input
            type="file"
            accept=".dxf,.dwg"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />

          <select value={outputType} onChange={(e) => setOutputType(e.target.value)}>
            <option value="pdf">PDF</option>
            <option value="png">PNG</option>
           
          </select>

          <button
            onClick={createJob}
            disabled={uploading}
            style={{
              padding: "10px 14px",
              borderRadius: 10,
              border: "1px solid #333",
              background: uploading ? "#201c1c" : "#241e1e",
              cursor: uploading ? "not-allowed" : "pointer",
              fontWeight: 600,
              
            }}
          >
            {uploading ? "Uploading..." : "Convert"}
          </button>
        </div>

        {error && (
          <div style={{ marginTop: 12, color: "crimson" }}>
            {error}
          </div>
        )}

        {jobId && (
          <div style={{ marginTop: 14 }}>
            <div><b>Job ID:</b> <code>{jobId}</code></div>
          </div>
        )}

        {job && (
          <div style={{ marginTop: 14 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <div><b>Status:</b> {job.status}</div>
              <div><b>Progress:</b> {job.progress}%</div>
            </div>

            <div style={{ marginTop: 8, color: "#444" }}>{job.message}</div>

            <div style={{ marginTop: 12, height: 10, background: "#151414", borderRadius: 8 }}>
              <div
                style={{
                  height: 10,
                  width: `${job.progress || 0}%`,
                  background: "#111",
                  borderRadius: 8,
                  transition: "width 0.3s ease",
                }}
              />
            </div>

            {job.status === "failed" && (
              <pre style={{ marginTop: 12, background: "#512828", padding: 12, borderRadius: 10, overflowX: "auto" }}>
                {job.error}
              </pre>
            )}

            {job.download_ready && (
              <a
                href={downloadUrl}
                style={{
                  display: "inline-block",
                  marginTop: 14,
                  padding: "10px 14px",
                  borderRadius: 10,
                  border: "1px solid #333",
                  textDecoration: "none",
                  color: "#111",
                  fontWeight: 700,
                }}
              >
                Download
              </a>
            )}
          </div>
        )}
      </div>

      
    </div>
  );
}