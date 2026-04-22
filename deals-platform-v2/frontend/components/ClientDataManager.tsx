"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface ClientDataManagerProps {
  module: "cs3" | "cs4";
  title: string;
}

export function ClientDataManager({ module, title }: ClientDataManagerProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  const endpoint = module === "cs3" ? "/post-deal/mock-client-data/cs3" : "/working-capital/mock-client-data";

  const loadData = async () => {
    setLoading(true);
    try {
      const response = await fetch(`http://localhost:8000${endpoint}`);
      if (!response.ok) throw new Error(`Failed to load ${module} data`);
      const loaded = await response.json();
      setData(loaded);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [module]);

  const downloadData = () => {
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${module}_client_data_${new Date().toISOString().split("T")[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const content = await file.text();
      const parsed = JSON.parse(content);
      setLoading(true);
      const response = await fetch(`http://localhost:8000${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(parsed),
      });
      if (!response.ok) throw new Error("Failed to upload data");
      const result = await response.json();
      setData(result.data || parsed);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setLoading(false);
      setEditing(false);
    }
  };

  return (
    <div className="panel p-4 space-y-4 border border-neutral-dark-secondary">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-neutral-white">{title}</h4>
        <span className="text-xs text-neutral-light-tertiary bg-neutral-dark-tertiary px-2 py-1 rounded">
          Mock Data
        </span>
      </div>

      {error && (
        <div className="bg-data-red/10 border border-data-red rounded p-2">
          <p className="text-sm text-data-red">{error}</p>
        </div>
      )}

      {data && !editing && (
        <div className="space-y-2">
          <pre className="bg-neutral-black p-2 rounded text-xs text-neutral-light-secondary overflow-auto max-h-48">
            {JSON.stringify(data, null, 2)}
          </pre>

          <div className="flex gap-2 flex-wrap">
            <button
              onClick={downloadData}
              className="btn text-xs px-3 py-1 hover:bg-neutral-dark-tertiary"
            >
              📥 Download
            </button>
            <button
              onClick={() => setEditing(true)}
              className="btn text-xs px-3 py-1 hover:bg-neutral-dark-tertiary"
            >
              ✏️ Upload New
            </button>
          </div>
        </div>
      )}

      {editing && (
        <div className="space-y-2">
          <div className="border-2 border-dashed border-neutral-dark-secondary rounded p-4 text-center">
            <input
              type="file"
              accept=".json"
              onChange={handleFileUpload}
              className="hidden"
              id={`upload-${module}`}
            />
            <label
              htmlFor={`upload-${module}`}
              className="text-sm text-neutral-light-secondary cursor-pointer hover:text-neutral-white"
            >
              Drag and drop JSON file or click to select
            </label>
          </div>
          <button
            onClick={() => setEditing(false)}
            className="btn text-xs px-3 py-1"
          >
            Cancel
          </button>
        </div>
      )}

      {loading && (
        <div className="text-center">
          <p className="text-xs text-neutral-light-tertiary">Loading...</p>
        </div>
      )}
    </div>
  );
}
