"use client";

import React, { useState } from "react";

interface ObservacaoMaestroProps {
  toolName: string;
  toolArgs?: Record<string, unknown>;
  toolResult?: Record<string, unknown>;
  children: React.ReactNode;
}

export default function ObservacaoMaestro({
  toolName,
  toolArgs,
  toolResult,
  children,
}: ObservacaoMaestroProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border border-[#26A69A]/40 bg-[#1A1D27] p-4 my-2">
      {/* Badge da fonte */}
      <div className="flex items-center justify-between mb-3">
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-[#26A69A]/10 border border-[#26A69A]/30 text-[#26A69A] text-xs font-mono">
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3H5a2 2 0 00-2 2v4m6-6h10a2 2 0 012 2v4M9 3v18m0 0h10a2 2 0 002-2V9M9 21H5a2 2 0 01-2-2V9m0 0h18" />
          </svg>
          {toolName}
        </span>

        {toolResult && (
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-xs text-[#6b7280] hover:text-[#26A69A] transition-colors flex items-center gap-1"
          >
            Por quê?
            <svg
              className={`w-3 h-3 transition-transform ${expanded ? "rotate-180" : ""}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        )}
      </div>

      {/* Conteúdo principal */}
      <div className="text-[#D1D4DC] text-sm leading-relaxed">{children}</div>

      {/* Dados brutos expandíveis */}
      {expanded && toolResult && (
        <div className="mt-3 pt-3 border-t border-[#2A2D3A]">
          {toolArgs && Object.keys(toolArgs).length > 0 && (
            <div className="mb-2">
              <p className="text-xs text-[#6b7280] mb-1">Parâmetros:</p>
              <pre className="text-xs text-[#6b7280] bg-[#0F1117] rounded p-2 overflow-x-auto">
                {JSON.stringify(toolArgs, null, 2)}
              </pre>
            </div>
          )}
          <p className="text-xs text-[#6b7280] mb-1">Dados brutos:</p>
          <pre className="text-xs text-[#6b7280] bg-[#0F1117] rounded p-2 overflow-x-auto max-h-48">
            {JSON.stringify(toolResult, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
