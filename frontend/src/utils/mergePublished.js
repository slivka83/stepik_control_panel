export function mergePublishedIntoSubmissions(submissions, publishedSolutions) {
  if (!submissions) return submissions;
  const publishedByMonth = new Map((publishedSolutions?.months || []).map((m) => [m?.month, Number(m?.dark) || 0]));
  return {
    ...submissions,
    months: (submissions.months || []).map((m) => ({
      ...m,
      published: publishedByMonth.get(m?.month) || 0,
    })),
  };
}
