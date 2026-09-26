interface Props {
  kind: string;
  children: string;
}

/** Small coloured label for categories, priorities, statuses and cache state. */
export function Badge({ kind, children }: Props) {
  return <span className={`badge badge-${kind}`}>{children.replace("_", " ")}</span>;
}
