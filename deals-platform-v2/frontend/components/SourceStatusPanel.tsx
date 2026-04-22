"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface SourceStatus {
  id: string;
  name: string;
  status: "ok" | "error" | "skipped" | "unknown";
  required: boolean;
  mocked: boolean;
  last_attempt_at: string | null;
  detail: string | null;
  mode: string;
}

interface ModuleReport {
  module: string;
  overall: string;
  sources: SourceStatus[];
}

export function SourceStatusPanel({ module }: { module?: string }) {
  const [reports, setReports] = useState<ModuleReport[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchStatus = async () => {
    setLoading(true);
    try {
      const response = await api.getSourceStatus(module);
      setReports(response.modules || []);
    } catch (e) {
      console.error("Failed to fetch source status:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000); // Refresh every 10s
    return () => clearInterval(interval);
  }, [module]);

  if (!reports.length && !loading) {
    return null;
  }

  return (
    <div className="space-y-4">
      {reports.map((report) => (
        <div
          key={report.module}
          className="panel p-4 space-y-3 border border-neutral-dark-secondary"
        >
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-semibold text-neutral-white capitalize">
              {report.module.replace("_", " ")}
            </h4>
            <div
              className={`w-2 h-2 rounded-full ${
                report.overall === "ok"
                  ? "bg-data-green"
                  : report.overall === "error"
                    ? "bg-data-red"
                    : "bg-data-yellow"
              }`}
              title={`Overall: ${report.overall}`}
            />
          </div>

          <div className="space-y-2">
            {report.sources.map((source) => (
              <div key={source.id} className="flex items-center gap-2 text-xs">
                {/* Status indicator */}
                <span
                  className={`w-2 h-2 rounded-full flex-shrink-0 ${
                    source.status === "ok"
                      ? "bg-data-green"
                      : source.status === "error"
                        ? "bg-data-red"
                        : source.status === "skipped"
                          ? "bg-neutral-dark-tertiary"
                          : "bg-neutral-dark-secondary"
                  }`}
                  title={
                    source.detail ? source.detail : `Status: ${source.status}`
                  }
                />

                {/* Source name */}
                <span className="text-neutral-light-secondary flex-1">
                  {source.name}
                </span>

                {/* Required/Mocked badge */}
                <div className="flex gap-1">
                  {source.required && (
                    <span className="px-1.5 py-0.5 bg-data-red/20 text-data-red rounded text-xs">
                      Required
                    </span>
                  )}
                  {source.mocked && (
                    <span className="px-1.5 py-0.5 bg-data-yellow/20 text-data-yellow rounded text-xs">
                      Mocked
                    </span>
                  )}
                </div>

                {/* Last attempt time */}
                {source.last_attempt_at && (
                  <span className="text-neutral-dark-tertiary text-xs">
                    {new Date(source.last_attempt_at).toLocaleTimeString()}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
