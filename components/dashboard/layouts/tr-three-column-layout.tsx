"use client"

import type { ReactNode } from "react"

type TrThreeColumnLayoutProps = {
  mapSlot: ReactNode
  timelineSlot: ReactNode
  detailSlot: ReactNode
}

/**
 * 3-column layout: Location(Map), Schedule(Timeline), Detail
 * AGENTS: Where / When / What in 3-column structure on large screens.
 */
export function TrThreeColumnLayout({
  mapSlot,
  timelineSlot,
  detailSlot,
}: TrThreeColumnLayoutProps) {
  return (
    <div
      className="grid flex-1 min-h-0 gap-4 sm:grid-cols-1 md:min-h-[480px] md:grid-cols-[minmax(260px,_1fr)_minmax(0,_2fr)] lg:grid-cols-[minmax(260px,_1fr)_minmax(0,_2fr)_minmax(280px,_1fr)]"
      data-testid="tr-three-column-layout"
    >
      <aside
        id="map"
        className="min-h-[240px] md:min-h-0 rounded-xl border border-accent/20 bg-card/60 p-4"
        aria-label="Location (Map)"
      >
        <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-muted-foreground">
          Location (Map)
        </h3>
        {mapSlot}
      </aside>
      <main
        className="flex min-h-[320px] md:min-h-0 flex-col flex-1 rounded-xl border border-accent/20 bg-card/60 p-4"
        aria-label="Schedule (Timeline)"
      >
        <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-muted-foreground">
          Schedule (Timeline)
        </h3>
        {timelineSlot}
      </main>
      <aside
        className="min-h-[240px] md:min-h-0 rounded-xl border border-accent/20 bg-card/60 p-4"
        aria-label="Detail"
      >
        <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-muted-foreground">
          Detail
        </h3>
        {detailSlot}
      </aside>
    </div>
  )
}
