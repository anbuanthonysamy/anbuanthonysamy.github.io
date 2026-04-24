"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { SourceStatusPanel } from "./SourceStatusPanel";
import type { SituationV2 } from "@/lib/types";

export function ScannerPanel() {
  const [scanning, setScanning] = useState(false);
  const [geography, setGeography] = useState<"worldwide" | "uk_only">("worldwide");
  const [lastScanTime, setLastScanTime] = useState<string | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);
  const [scanResult, setScanResult] = useState<any>(null);

  const handleScan = async () => {
    setScanning(true);
    setScanError(null);
    try {
      const result = await api.triggerScan("live", geography);
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
