interface PlaceholderPageProps {
  title: string
  /** Roadmap stage that implements the page (notes/frontend/tasks_frontend.md). */
  stage: string
}

/** Temporary page until the real one is built in its stage. */
export function PlaceholderPage({ title, stage }: PlaceholderPageProps) {
  return (
    <section>
      <h1 className="text-2xl font-semibold">{title}</h1>
      <p className="mt-2 text-slate-500">Coming in {stage}.</p>
    </section>
  )
}
