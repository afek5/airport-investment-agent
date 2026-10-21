import { cn } from "@/lib/utils";

/** Plain, well-typeset evidence tables: mono uppercase headers, right-aligned tabular numbers, hairline rows. */
export function DataTable({
  caption,
  children,
  className,
  testId,
}: {
  caption?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  testId?: string;
}) {
  return (
    <div className={cn("-mx-1 overflow-x-auto px-1", className)} data-testid={testId}>
      <table className="w-full border-collapse text-[12.5px] leading-[1.45]">
        {caption ? <caption className="eyebrow pb-1.5 text-left">{caption}</caption> : null}
        {children}
      </table>
    </div>
  );
}

export function Th({
  children,
  num,
  className,
  title,
}: {
  children?: React.ReactNode;
  num?: boolean;
  className?: string;
  title?: string;
}) {
  return (
    <th
      scope="col"
      title={title}
      className={cn(
        "num whitespace-nowrap pb-1.5 pr-3 align-bottom text-[11px] font-medium uppercase tracking-[0.06em] text-[var(--ink-muted)] last:pr-0",
        num ? "text-right" : "text-left",
        className,
      )}
    >
      {children}
    </th>
  );
}

export function Td({
  children,
  num,
  className,
  colSpan,
}: {
  children?: React.ReactNode;
  num?: boolean;
  className?: string;
  colSpan?: number;
}) {
  return (
    <td
      colSpan={colSpan}
      className={cn("py-1.5 pr-3 align-top last:pr-0", num && "num whitespace-nowrap text-right", className)}
    >
      {children}
    </td>
  );
}

export function Tr({ children, className }: { children: React.ReactNode; className?: string }) {
  return <tr className={cn("border-t border-[var(--hairline)]", className)}>{children}</tr>;
}

export function EvidenceTitle({ code, title, sub }: { code?: string; title: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <header className="space-y-0.5">
      <h3 className="text-[15px] font-semibold leading-snug">
        {code ? <span className="num mr-1.5">{code}</span> : null}
        {title}
      </h3>
      {sub ? <p className="text-xs text-[var(--ink-muted)]">{sub}</p> : null}
    </header>
  );
}

export function Block({
  label,
  tag,
  children,
  testId,
}: {
  label: string;
  tag?: React.ReactNode;
  children: React.ReactNode;
  testId?: string;
}) {
  return (
    <section className="space-y-2 border-t border-[var(--hairline)] pt-3" data-testid={testId}>
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="eyebrow">{label}</h4>
        {tag}
      </div>
      {children}
    </section>
  );
}

export function Muted({ children }: { children: React.ReactNode }) {
  return <span className="text-[var(--ink-muted)]">{children}</span>;
}
