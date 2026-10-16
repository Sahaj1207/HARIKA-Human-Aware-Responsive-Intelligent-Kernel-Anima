/**
 * Small set of Apple-style controls shared by the main window, the orb and
 * Settings: grouped (inset) lists, rows, switches, segmented controls,
 * buttons and the colored icon tiles used in System Settings.
 */
import React from 'react';
import { ChevronRight } from 'lucide-react';

export const GroupedSection: React.FC<{ title?: string; footer?: React.ReactNode; children: React.ReactNode }> = ({
  title,
  footer,
  children,
}) => (
  <section className="space-y-1.5">
    {title && <h3 className="t-footnote text-label-2 px-4">{title}</h3>}
    <div className="rounded-xl bg-surface dark:bg-surface-2 overflow-hidden divide-y divide-separator">{children}</div>
    {footer && <p className="t-footnote text-label-2 px-4 pt-0.5">{footer}</p>}
  </section>
);

export const IconTile: React.FC<{ color: string; children: React.ReactNode }> = ({ color, children }) => (
  <span
    className="inline-grid place-items-center w-7 h-7 rounded-[7px] text-white shrink-0 shadow-[inset_0_-1px_0_rgba(0,0,0,0.12)]"
    style={{ background: color }}
    aria-hidden
  >
    {children}
  </span>
);

interface RowProps {
  icon?: React.ReactNode;
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  value?: React.ReactNode;
  accessory?: React.ReactNode;
  onClick?: () => void;
  chevron?: boolean;
  destructive?: boolean;
}

export const Row: React.FC<RowProps> = ({ icon, title, subtitle, value, accessory, onClick, chevron, destructive }) => {
  const content = (
    <>
      {icon}
      <span className="flex-1 min-w-0 text-left">
        <span className={`block t-callout truncate ${destructive ? 'text-danger' : 'text-label'}`}>{title}</span>
        {subtitle && <span className="block t-footnote text-label-2 mt-0.5">{subtitle}</span>}
      </span>
      {value !== undefined && <span className="t-callout text-label-2 truncate max-w-[45%]">{value}</span>}
      {accessory}
      {chevron && <ChevronRight className="w-4 h-4 text-label-3 shrink-0" aria-hidden />}
    </>
  );
  const base = 'w-full flex items-center gap-3 px-4 min-h-11 py-2.5';
  return onClick ? (
    <button type="button" onClick={onClick} className={`${base} active:bg-fill hover:bg-fill/60 transition-colors cursor-default`}>
      {content}
    </button>
  ) : (
    <div className={base}>{content}</div>
  );
};

export const Toggle: React.FC<{ checked: boolean; onChange: (checked: boolean) => void; label: string; disabled?: boolean }> = ({
  checked,
  onChange,
  label,
  disabled,
}) => (
  <button
    type="button"
    role="switch"
    aria-checked={checked}
    aria-label={label}
    disabled={disabled}
    onClick={() => onChange(!checked)}
    className={`relative w-[51px] h-[31px] rounded-full transition-colors duration-200 shrink-0 disabled:opacity-40 ${
      checked ? 'bg-ok' : 'bg-fill-2'
    }`}
  >
    <span
      className={`absolute top-[2px] left-[2px] w-[27px] h-[27px] rounded-full bg-white shadow-[0_3px_8px_rgba(0,0,0,0.15),0_1px_1px_rgba(0,0,0,0.16)] transition-transform duration-200 ${
        checked ? 'translate-x-[20px]' : ''
      }`}
    />
  </button>
);

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex p-0.5 rounded-[9px] bg-fill">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="radio"
          aria-checked={value === option.value}
          onClick={() => onChange(option.value)}
          className={`px-3.5 py-1 t-footnote font-medium rounded-[7px] transition-all ${
            value === option.value ? 'bg-surface text-label shadow-[0_3px_8px_rgba(0,0,0,0.12),0_0_0_0.5px_rgba(0,0,0,0.04)]' : 'text-label'
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

type ButtonKind = 'filled' | 'tinted' | 'plain';

export const Button: React.FC<
  React.ButtonHTMLAttributes<HTMLButtonElement> & { kind?: ButtonKind; destructive?: boolean }
> = ({ kind = 'filled', destructive, className = '', children, ...rest }) => {
  // Full class names (Tailwind only generates classes it can see in source).
  const styles: Record<ButtonKind, string> = destructive
    ? { filled: 'bg-danger text-white hover:brightness-110', tinted: 'bg-danger/15 text-danger hover:bg-danger/20', plain: 'text-danger hover:opacity-80' }
    : { filled: 'bg-accent text-white hover:brightness-110', tinted: 'bg-accent/15 text-accent hover:bg-accent/20', plain: 'text-accent hover:opacity-80' };
  return (
    <button
      type="button"
      {...rest}
      className={`inline-flex items-center justify-center gap-1.5 rounded-full px-4 py-1.5 t-callout font-medium transition-all active:scale-[0.98] disabled:opacity-40 disabled:pointer-events-none ${styles[kind]} ${className}`}
    >
      {children}
    </button>
  );
};
