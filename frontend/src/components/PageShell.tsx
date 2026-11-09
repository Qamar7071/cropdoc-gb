import type { ReactNode } from "react";

/* Dark-green title band + content container used by every page except the Scanner. */
export function PageShell({ title, lead, children, actions }: { title: string; lead?: string; children: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-backdrop min-h-[60vh]">
      <div className="mx-auto max-w-[1280px] px-4 pt-8 pb-6 lg:px-8">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl">{title}</h1>
            {lead && <p className="mt-2 max-w-3xl text-base text-white/90 sm:text-lg">{lead}</p>}
          </div>
          {actions}
        </div>
      </div>
      <div className="mx-auto max-w-[1280px] space-y-5 px-4 pb-6 lg:px-8">{children}</div>
    </div>
  );
}
