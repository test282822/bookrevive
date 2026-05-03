"use client";

interface Props {
  epubUrl: string;
  epubName: string;
  title: string;
  pageCount: number;
  onReset: () => void;
}

export default function ResultCard({ epubUrl, epubName, title, pageCount, onReset }: Props) {
  return (
    <div className="bg-stone-900 border border-stone-700 rounded-2xl p-6 space-y-5 fade-up">
      {/* Success icon */}
      <div className="text-center">
        <div className="text-5xl mb-3">✅</div>
        <h2 className="font-serif text-xl text-amber-400">{title}</h2>
        <p className="text-stone-400 text-sm mt-1">
          {pageCount} page{pageCount > 1 ? "s" : ""} digitized successfully
        </p>
      </div>

      {/* Download */}
      <a
        href={epubUrl}
        download={epubName}
        className="block w-full bg-amber-500 text-stone-950 font-semibold rounded-2xl py-4 text-center text-base active:bg-amber-400 transition-colors"
      >
        Download EPUB
      </a>

      <p className="text-stone-600 text-xs text-center">
        Open with Books, Kindle, or any EPUB reader
      </p>

      {/* AD SLOT — between result and reset (high visibility placement) */}
      {/* <AdSlot slot="result-inline" /> */}

      <button
        onClick={onReset}
        className="w-full text-stone-500 border border-stone-800 rounded-2xl py-3 text-sm active:bg-stone-900"
      >
        Digitize another book
      </button>
    </div>
  );
}
