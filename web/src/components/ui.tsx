import { useEffect, useRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { X } from "lucide-react";
import { cssColor, initials, titleHue } from "../lib/colors";
import { api, type Character, type Novel } from "../lib/api";

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

type Variant = "primary" | "ghost" | "outline" | "danger";

/** Button styling, also for links that should look like buttons (never nest <button> in <a>). */
export function buttonCls(variant: Variant = "outline", size: "sm" | "md" = "md", className?: string) {
  return cx(
    "inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
    size === "sm" ? "h-8 px-2.5 text-[13px]" : "h-10 px-3.5 text-sm",
    variant === "primary" && "bg-accent text-accent-ink hover:brightness-110",
    variant === "ghost" && "text-muted hover:bg-raised hover:text-text",
    variant === "outline" && "border border-line bg-surface text-text hover:bg-raised",
    variant === "danger" && "border border-danger/40 text-danger hover:bg-danger/10",
    className,
  );
}

export function Button({
  variant = "outline",
  size = "md",
  className,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md" }) {
  return <button {...rest} className={buttonCls(variant, size, className)} />;
}

export function IconButton({ label, className, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button
      aria-label={label}
      title={label}
      {...rest}
      className={cx(
        "inline-flex h-9 w-9 items-center justify-center rounded-lg text-muted transition-colors hover:bg-raised hover:text-text disabled:opacity-40",
        className,
      )}
    />
  );
}

export function Avatar({ character, name, size = 36 }: { character?: Character | null; name?: string; size?: number }) {
  const label = character?.name ?? name ?? "?";
  const color = character ? cssColor(character.color) : "var(--faint)";
  return (
    <div
      aria-hidden
      className="flex shrink-0 select-none items-center justify-center rounded-full font-semibold"
      style={{
        width: size,
        height: size,
        fontSize: size * 0.36,
        color,
        background: `color-mix(in oklab, ${color} 18%, var(--surface))`,
        boxShadow: `inset 0 0 0 1.5px color-mix(in oklab, ${color} 55%, transparent)`,
      }}
    >
      {initials(label)}
    </div>
  );
}

export function Cover({ novel, className }: { novel: Pick<Novel, "id" | "title" | "author" | "has_cover" | "updated_at">; className?: string }) {
  if (novel.has_cover) {
    return (
      <img
        src={api.coverUrl(novel.id, novel.updated_at)}
        alt=""
        loading="lazy"
        className={cx("aspect-[2/3] w-full rounded-lg object-cover shadow-md ring-1 ring-line", className)}
      />
    );
  }
  return (
    <div
      className={cx("cover-fallback flex aspect-[2/3] w-full flex-col justify-end rounded-lg p-3 shadow-md ring-1 ring-line", className)}
      style={{ ["--hue" as string]: titleHue(novel.title) }}
    >
      <div className="font-serif text-base font-semibold leading-tight text-text">{novel.title}</div>
      {novel.author && <div className="mt-1 text-xs text-muted">{novel.author}</div>}
    </div>
  );
}

export function ProgressBar({ value, max, tone = "accent", label }: { value: number; max: number; tone?: "accent" | "ok"; label?: string }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-label={label}
      className="h-1.5 w-full overflow-hidden rounded-full bg-raised"
    >
      <div className={cx("h-full rounded-full transition-[width] duration-500", tone === "ok" ? "bg-ok" : "bg-accent")} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      className={cx(
        "m-auto w-[calc(100%-2rem)] rounded-2xl border border-line bg-surface p-0 text-text shadow-2xl backdrop:bg-black/50 backdrop:backdrop-blur-sm",
        wide ? "max-w-2xl" : "max-w-md",
      )}
    >
      {open && (
        <div className="p-5">
          <div className="mb-4 flex items-center justify-between gap-4">
            <h2 className="text-base font-semibold">{title}</h2>
            <IconButton label="Close" onClick={onClose}>
              <X size={18} />
            </IconButton>
          </div>
          {children}
        </div>
      )}
    </dialog>
  );
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-muted">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-faint">{hint}</span>}
    </label>
  );
}

export const inputCls =
  "h-10 w-full rounded-lg border border-line bg-bg px-3 text-sm text-text placeholder:text-faint focus:border-accent focus:outline-none";

export function Spinner({ size = 18 }: { size?: number }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className="inline-block animate-spin rounded-full border-2 border-line border-t-accent"
      style={{ width: size, height: size }}
    />
  );
}

export function Empty({ icon, title, children }: { icon: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center px-4 py-16 text-center">
      <div className="mb-4 text-faint">{icon}</div>
      <h2 className="text-lg font-semibold">{title}</h2>
      {children && <div className="mt-2 text-sm text-muted">{children}</div>}
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <div role="alert" className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger">
      {error instanceof Error ? error.message : String(error)}
    </div>
  );
}
