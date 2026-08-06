import { useSync } from '../contexts/SyncContext';
import ErrorBanner from '../components/ErrorBanner';
import SubmissionsChart from '../components/SubmissionsChart';
import ActiveStudentsChart from '../components/ActiveStudentsChart';
import { formatMonthLabel } from '../utils/monthWindow.js';

export default function Activities() {
  const { data, error, refresh } = useSync();
  const submissions = data.submissions;
  const financials = data.financials;
  const community = financials?.community || {};
  const commentsMonthly = community.comments_monthly || {};

  const commentsChartData = {
    months: Object.entries(commentsMonthly)
      .map(([key, val]) => {
        const [y, m] = key.split('-');
        return { month: formatMonthLabel(Number(m), Number(y)), total: val, correct: val };
      })
      .sort((a, b) => a.month.localeCompare(b.month)),
  };

  return (
    <div className="flex flex-col flex-1 gap-4 min-h-0">
      {error && <ErrorBanner message={error} onRetry={refresh} />}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 flex-1 min-h-0">
        <ActiveStudentsChart data={data.activeStudents} hatched lightLabel="Уникальные студенты" tooltipRight />
        <ActiveStudentsChart
          data={data.certificates}
          title="Сертификаты"
          primaryColor="#B70094"
          secondaryColor="#DB62C4"
          hatched
          lightLabel="Обычные"
          darkLabel="С отличием"
          darkTooltipOverlap
        />
        <SubmissionsChart
          data={commentsChartData}
          title="Комментарии"
          primaryColor="#b8860b"
          secondaryColor="#6b4f0a"
          hideCorrectLegend
          hideTotalLegend
          tooltipRight
        />
        <SubmissionsChart data={submissions || {}} />
      </div>
    </div>
  );
}
