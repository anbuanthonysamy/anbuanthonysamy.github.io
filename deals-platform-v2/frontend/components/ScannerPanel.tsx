"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { SourceStatusPanel } from "./SourceStatusPanel";
import type { SituationV2 } from "@/lib/types";

export function ScannerPanel() {
  const [scanning, setScanning] = useState(false);
  const [apiMode, setApiMode] = useState<"live" | "offline" | "auto">("auto");
  const [geography, setGeography] = useState<"worldwide" | "uk_only">("worldwide");
  const [lastScanTime, setLastScanTime] = useState<string | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);
  const [scanResult, setScanResult] = useState<any>(null);
  const [modeStatus, setModeStatus] = useState<any>(null);
  const [loadingMode, setLoadingMode] = useState(false);

  useEffect(() => {
    // Load current mode on mount
    const loadMode = async () => {
      setLoadingMode(true);
      try {
        const status = await api.getMode();
        setModeStatus(status);
        setApiMode(status.effective_mode);
      } catch (e) {
        console.error("Failed to load mode:", e);
      } finally {
        setLoadingMode(false);
      }
    };
    loadMode();
  }, []);

  const handleModeChange = async (newMode: "live" | "offline") => {
    setApiMode(newMode);
    try {
      await api.setMode(newMode);
    } catch (e) {
      console.error("Failed to set mode:", e);
      setScanError("Failed to save mode preference");
    }
  };

  const handleScan = async () => {
    setScanning(true);
    setScanError(null);
    try {
      const scanMode = apiMode === "auto" ? modeStatus?.effective_mode : apiMode;
      const result = await api.triggerScan(scanMode, geography);
      setScanResult(result);
      setLastScanTime(new Date().toLocaleTimeString());
    } catch (e: unknown) {
      setScanError(e instanceof Error ? e.message : "Scan failed");
    } finally {
      setScanning(false);
    }
  };

  return (
    <div className="panel p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-neutral-white">Market Scanner</h3>
          <p className="text-xs text-neutral-light-tertiary mt-1">
            Continuous scanning of {geography === "worldwide" ? "S&P 500 + FTSE 100" : "FTSE 100"} companies
          </p>
        </div>
        {lastScanTime && (
          <div className="text-right">
            <div className="text-xs text-neutral-light-tertiary">Last scan</div>
            <div className="text-sm font-mono text-neutral-white">{lastScanTime}</div>
          </div>
        )}
      </div>

      <div className="flex gap-2 flex-wrap items-center">
        {/* API Mode Toggle */}
        <div className="flex items-center gap-1 border border-neutral-dark-secondary rounded px-2 py-1">
          <span className="text-xs text-neutral-light-tertiary">Mode:</span>
          {!loadingMode && (
            <>
              <button
                onClick={() => handleModeChange("offline")}
                className={`text-sm px-2 py-0.5 rounded transition-colors ${
                  apiMode === "offline"
                    ? "bg-neutral-white text-neutral-black"
                    : "text-neutral-light-secondary hover:text-neutral-white"
                }`}
              >
                Offline
              </button>
              <span className="text-neutral-dark-tertiary">•</span>
              <button
                onClick={() => handleModeChange("live")}
                className={`text-sm px-2 py-0.5 rounded transition-colors ${
                  apiMode === "live"
                    ? "bg-data-green/30 text-data-green"
                    : "text-neutral-light-secondary hover:text-neutral-white"
                }`}
              >
                Live
              </button>
            </>
          )}
        </div>

        {/* API availability indicator */}
        {modeStatus && (
          <div className="text-xs text-neutral-light-tertiary flex gap-1">
            {modeStatus.available_keys.EDGAR_USER_AGENT && (
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-data-green" />
                EDGAR
              </span>
            )}
            {modeStatus.available_keys.COMPANIES_HOUSE && (
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-data-green" />
                CH
              </span>
            )}
          </div>
        )}

        {/* Geography Toggle */}
        <div className="flex items-center gap-1 border border-neutral-dark-secondary rounded px-2 py-1">
          <span className="text-xs text-neutral-light-tertiary">Geography:</span>
          <select
            value={geography}
            onChange={(e) => setGeography(e.target.value as "worldwide" | "uk_only")}
            className="bg-transparent text-sm text-neutral-white outline-none cursor-pointer"
          >
            <option value="worldwide">Worldwide</option>
            <option value="uk_only">UK Only</option>
          </select>
        </div>

        {/* Scan Button */}
        <button
          onClick={handleScan}
          disabled={scanning}
          className="btn text-sm px-3 py-1 disabled:opacity-50"
        >
          {scanning ? "Scanning…" : "Refresh Now"}
        </button>
      </div>

      {scanError && (
        <div className="bg-data-red/10 border border-data-red rounded p-2">
          <p className="text-sm text-data-red">{scanError}</p>
        </div>
      )}

      {scanResult && (
        <div className="bg-data-green/10 border border-data-green rounded p-2">
          <p className="text-sm text-data-green font-semibold">Scan complete</p>
          <div className="text-xs text-neutral-light-tertiary mt-1 space-y-1">
            <div>CS1 Origination: {scanResult.counts?.cs1_origination || 0} situations</div>
            <div>CS2 Carve-outs: {scanResult.counts?.cs2_carve_outs || 0} situations</div>
            <div>Total: {scanResult.total || 0} situations</div>
          </div>
        </div>
      )}

      {/* Source status panel for CS1 and CS2 */}
      <SourceStatusPanel module="origination" />
      <SourceStatusPanel module="carve_outs" />
    </div>
  );
}
