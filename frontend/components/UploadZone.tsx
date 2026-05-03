"use client";

import { useRef, useState } from "react";

interface Props {
  files: File[];
  onChange: (files: File[]) => void;
}

export default function UploadZone({ files, onChange }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  const addFiles = (incoming: FileList | null) => {
    if (!incoming) return;
    const valid = Array.from(incoming).filter((f) =>
      f.type.startsWith("image/")
    );
    onChange([...files, ...valid]);
  };

  const removeFile = (index: number) => {
    const next = [...files];
    next.splice(index, 1);
    onChange(next);
  };

  return (
    <div className="space-y-3">
      {/* Drop zone */}
      <div
        className={`upload-zone border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all ${
          dragging
            ? "border-amber-500 bg-amber-500/8 drag-over"
            : "border-stone-700 bg-stone-900/50 active:bg-stone-900"
        }`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          addFiles(e.dataTransfer.files);
        }}
      >
        <div className="text-4xl mb-3">📚</div>
        <p className="text-stone-300 font-medium text-base">
          Tap to add photos
        </p>
        <p className="text-stone-500 text-sm mt-1">
          Camera roll, Files app, or drag & drop
        </p>
        <p className="text-stone-600 text-xs mt-3">
          JPG · PNG · WEBP · TIFF
        </p>

        {/* Hidden input — accept="image/*" triggers camera roll on iPhone */}
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          multiple
          capture={undefined}
          className="hidden"
          onChange={(e) => addFiles(e.target.files)}
        />
      </div>

      {/* File list */}
      {files.length > 0 && (
        <div className="space-y-2 fade-up">
          <p className="text-xs text-stone-500 uppercase tracking-wider">
            {files.length} page{files.length > 1 ? "s" : ""} queued
          </p>
          <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
            {files.map((f, i) => (
              <div
                key={`${f.name}-${i}`}
                className="flex items-center justify-between bg-stone-900 rounded-xl px-3 py-2"
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className="text-stone-600 text-xs w-5 text-right shrink-0">
                    {i + 1}
                  </span>
                  <span className="text-stone-300 text-sm truncate">{f.name}</span>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); removeFile(i); }}
                  className="text-stone-600 hover:text-red-400 text-lg leading-none shrink-0 ml-2 active:text-red-400"
                  aria-label="Remove"
                >
                  ×
                </button>
              </div>
            ))}
          </div>

          <button
            onClick={() => inputRef.current?.click()}
            className="text-xs text-amber-500 border border-amber-900 rounded-full px-4 py-1.5 active:bg-amber-950"
          >
            + Add more pages
          </button>
        </div>
      )}
    </div>
  );
}
