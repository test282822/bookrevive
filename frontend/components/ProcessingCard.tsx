"use client";

interface Props {
  pageCount: number;
}

export default function ProcessingCard({ pageCount }: Props) {
  return (
    <div className="bg-stone-900 rounded-2xl p-6 text-center space-y-4 fade-up">
      {/* Spinner */}
      <div className="flex justify-center">
        <div className="w-12 h-12 rounded-full border-2 border-stone-700 border-t-amber-500 animate-spin" />
      </div>

      <div>
        <p className="text-stone-200 font-medium">Digitizing your book</p>
        <p className="text-stone-500 text-sm mt-1">
          Processing {pageCount} page{pageCount > 1 ? "s" : ""} — this may take a minute
        </p>
      </div>

      {/* Shimmer steps */}
      <div className="space-y-2 text-left">
        {["Preprocessing images", "Running OCR", "Building EPUB"].map((step, i) => (
          <div key={step} className="flex items-center gap-3">
            <div
              className="w-1.5 h-1.5 rounded-full bg-amber-500"
              style={{ opacity: 0.3 + i * 0.3 }}
            />
            <div className="flex-1 h-3 rounded shimmer" style={{ animationDelay: `${i * 0.2}s` }} />
            <span className="text-stone-600 text-xs">{step}</span>
          </div>
        ))}
      </div>

      <p className="text-stone-600 text-xs">
        Don't close this tab
      </p>
    </div>
  );
}
