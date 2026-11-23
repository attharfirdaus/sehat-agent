// Teks respons backend/LLM dengan markdown ringan, dirender sebagai elemen React (tanpa HTML
// mentah): ### judul, #### sub-judul, - atau 1. list, > catatan, **tebal**, [SOURCE-ID](url) chip.

const INLINE = /\*\*(.+?)\*\*|\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g;

function inline(text: string, keyPrefix: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(INLINE)) {
    out.push(text.slice(last, m.index));
    const key = `${keyPrefix}-${m.index}`;
    if (m[1] !== undefined) {
      out.push(
        <strong key={key} className="font-semibold text-foreground">
          {m[1]}
        </strong>,
      );
    } else {
      out.push(
        <a
          key={key}
          href={m[3]}
          target="_blank"
          rel="noopener noreferrer"
          className="mx-0.5 inline-flex items-center rounded-full border border-border bg-muted px-2 py-0.5 align-baseline text-xs font-medium whitespace-nowrap text-foreground underline-offset-2 hover:underline focus-visible:outline-2 focus-visible:outline-ring"
        >
          {m[2]}
        </a>,
      );
    }
    last = m.index + m[0].length;
  }
  out.push(text.slice(last));
  return out;
}

type Block =
  | { kind: "h3" | "h4" | "p" | "note"; text: string }
  | { kind: "ul" | "ol"; items: string[] };

function parse(text: string): Block[] {
  const blocks: Block[] = [];
  for (const raw of text.split("\n")) {
    const line = raw.trimEnd();
    const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);
    const prev = blocks.at(-1);
    if (bullet || numbered) {
      const kind = bullet ? "ul" : "ol";
      const item = (bullet ?? numbered)![1];
      if (prev && prev.kind === kind) prev.items.push(item);
      else blocks.push({ kind, items: [item] });
    } else if (line.startsWith("#### "))
      blocks.push({ kind: "h4", text: line.slice(5) });
    else if (/^#{1,3} /.test(line))
      blocks.push({ kind: "h3", text: line.replace(/^#{1,3} /, "") });
    else if (line.startsWith("> "))
      blocks.push({ kind: "note", text: line.slice(2) });
    else if (line.trim()) {
      // Baris biasa berurutan digabung jadi satu paragraf (baris baru tetap dipertahankan).
      if (prev && prev.kind === "p") prev.text += "\n" + line;
      else blocks.push({ kind: "p", text: line });
    } else blocks.push({ kind: "p", text: "" }); // baris kosong memutus paragraf
  }
  return blocks.filter((b) => b.kind !== "p" || b.text);
}

export function RichText({ text }: { text: string }) {
  return (
    <div className="flex flex-col gap-2 leading-relaxed break-words">
      {parse(text).map((b, i) => {
        const key = String(i);
        switch (b.kind) {
          case "h3":
            return (
              <h3
                key={key}
                className="mt-3 text-base font-bold tracking-tight text-foreground first:mt-0"
              >
                {inline(b.text, key)}
              </h3>
            );
          case "h4":
            return (
              <h4 key={key} className="mt-1 text-sm font-semibold text-primary">
                {inline(b.text, key)}
              </h4>
            );
          case "note":
            return (
              <p
                key={key}
                className="mt-1 border-t border-border pt-2 text-xs text-muted-foreground"
              >
                {inline(b.text, key)}
              </p>
            );
          case "ul":
          case "ol": {
            const List = b.kind === "ul" ? "ul" : "ol";
            return (
              <List
                key={key}
                className={`flex flex-col gap-1.5 pl-5 marker:text-primary ${b.kind === "ul" ? "list-disc" : "list-decimal"}`}
              >
                {b.items.map((item, j) => (
                  <li key={j} className="pl-1">
                    {inline(item, `${key}-${j}`)}
                  </li>
                ))}
              </List>
            );
          }
          default:
            return (
              <p key={key} className="whitespace-pre-line">
                {inline(b.text, key)}
              </p>
            );
        }
      })}
    </div>
  );
}
