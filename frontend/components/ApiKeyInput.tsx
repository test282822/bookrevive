"use client";

import { useState } from "react";

interface Props {
  value: string;
  onChange: (v: string) => void;
}

export default function ApiKeyInput({ value, onChange }: Props) {
  const [show, setShow] = useState(false);

  return (
    <div className="bg-stone-900 border border-stone-800 rounded-xl p-4 space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-xs text-stone-400 uppercase tracking-wider">
          Anthropic API Key
        </label>
        <span className="text-xs text-amber-600 bg-amber-950/50 px-2 py-0.5 rounded-full">
          Optional
        </span>
      </div>
      <p className="text-stone-600 text-xs">
        Enables AI fallback for blurry or faded pages. Your key is used only for this session and never stored.
      </p>
      <div className="flex gap-2">
        <input
          type={show ? "text" : "password"}
          placeholder="sk-ant-..."
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="off"
          spellCheck={false}
          className="flex-1 bg-stone-950 border border-stone-700 rounded-xl px-3 py-2.5 text-stone-300 placeholder-stone-700 text-sm focus:outline-none focus:border-amber-700 font-mono"
        />
        <button
          type="button"
          onClick={() => setShow(!show)}
          className="text-stone-500 border border-stone-700 rounded-xl px-3 text-xs active:bg-stone-800"
        >
          {show ? "Hide" : "Show"}
        </button>
      </div>
      <a
        href="https://console.anthropic.com"
        target="_blank"
        rel="noopener noreferrer"
        className="text-xs text-amber-600 underline"
      >
        Get a key at console.anthropic.com →
      </a>
    </div>
  );
}
