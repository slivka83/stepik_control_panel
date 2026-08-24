import { useSync } from '../contexts/SyncContext';
import KpiCard from '../components/KpiCard';
import RevenueChart from '../components/RevenueChart';
import SubmissionsChart from '../components/SubmissionsChart';
import StudentsBar from '../components/StudentsBar';
import ErrorBanner from '../components/ErrorBanner';
import { formatNumber } from '../utils/formatNumber';

function buildTrendTooltip(label, detail, pct, unit = '') {
  if (!detail || pct === null || pct === undefined) return null;
  const cur = `${formatNumber(detail.current)}${unit}`;
  const prev = `${formatNumber(detail.previous)}${unit}`;
  const sign = pct >= 0 ? '+' : '−';
  return [
    'Изменение за месяц',
    `${label}: сейчас ${cur}, в прошлом месяце ${prev}`,
    `Расчёт: (${cur} − ${prev}) ÷ ${prev} × 100 = ${sign}${Math.abs(pct)}%`,
  ].join('\n');
}

export default function Dashboard() {
  const { data, error, refresh } = useSync();
  const { kpi, cohorts, revenue, submissions } = data;

  return (
    <div className="flex flex-col flex-1 gap-4 min-h-0">
      {error && <ErrorBanner message={error} onRetry={refresh} />}

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <KpiCard
          title="Доход /месяц"
          value={kpi?.total_revenue || 0}
          trend={kpi?.revenue_change_pct}
          trendTooltip={buildTrendTooltip('Доход', kpi?.revenue_change_detail, kpi?.revenue_change_pct, ' ₽')}
          color="white"
          suffix={'\u200A₽'}
        />
        <KpiCard
          title="Покупки /месяц"
          value={kpi?.current_month_payments || 0}
          trend={kpi?.payments_change_pct}
          trendTooltip={buildTrendTooltip('Покупки', kpi?.payments_change_detail, kpi?.payments_change_pct)}
          color="white"
        />
        <KpiCard
          title="Курсы"
          value={kpi?.courses_published || 0}
          secondValue={kpi?.courses_unpublished || 0}
          color="white"
        />
        <KpiCard
          title="Студенты"
          value={kpi?.students_prev_months ?? 0}
          secondValue={kpi?.current_month_students || 0}
          trend={kpi?.students_change_pct}
          trendTooltip={buildTrendTooltip('Новые студенты', kpi?.students_change_detail, kpi?.students_change_pct)}
          secondHighlight
          color="white"
        />
        <KpiCard
          title="Средняя оценка шагов"
          value={kpi?.steps_average_grade || 0}
          ratingColor
          fractionDigits={2}
          minimumFractionDigits={2}
        />
        <KpiCard
          title="Средний рейтинг курсов"
          value={kpi?.average_rating || 0}
          ratingColor
          fractionDigits={2}
          minimumFractionDigits={2}
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <KpiCard
          title="Возвраты (₽) /месяц"
          value={kpi?.current_month_refunds_count || 0}
          trend={kpi?.refunds_change_pct}
          trendTooltip={buildTrendTooltip('Возвраты (₽)', kpi?.refunds_change_detail, kpi?.refunds_change_pct, ' ₽')}
          trendInverted
          color="white"
          suffix={'\u200A₽'}
        />
        <KpiCard
          title="Возвраты (шт) /месяц"
          value={kpi?.current_month_refunds_pcs || 0}
          trend={kpi?.refunds_pcs_change_pct}
          trendTooltip={buildTrendTooltip('Возвраты (шт)', kpi?.refunds_pcs_change_detail, kpi?.refunds_pcs_change_pct)}
          trendInverted
          color="white"
        />
        <KpiCard
          title="Сертификаты"
          value={kpi?.certificates_prev_months ?? 0}
          secondValue={kpi?.certificates_current_month || 0}
          trend={kpi?.certificates_change_pct}
          trendTooltip={buildTrendTooltip('Сертификаты', kpi?.certificates_change_detail, kpi?.certificates_change_pct)}
          secondHighlight
          color="white"
          trendBadge
        />
        <KpiCard
          title="Публичные решения"
          value={kpi?.published_solutions_prev_months ?? 0}
          secondValue={kpi?.published_solutions_current_month || 0}
          trend={kpi?.published_solutions_change_pct}
          trendTooltip={buildTrendTooltip(
            'Публичные решения',
            kpi?.published_solutions_change_detail,
            kpi?.published_solutions_change_pct,
          )}
          secondHighlight
          color="white"
          trendBadge
        />
        <KpiCard
          title="Комментарии"
          value={kpi?.comments_prev_months ?? 0}
          secondValue={kpi?.current_month_comments || 0}
          trend={kpi?.comments_change_pct}
          trendTooltip={buildTrendTooltip('Комментарии', kpi?.comments_change_detail, kpi?.comments_change_pct)}
          secondHighlight
          color="white"
          trendBadge
        />
        <KpiCard
          title="Отзывы"
          value={kpi?.reviews_prev_months ?? 0}
          secondValue={kpi?.reviews_current_month || 0}
          trend={kpi?.reviews_change_pct}
          trendTooltip={buildTrendTooltip('Отзывы', kpi?.reviews_change_detail, kpi?.reviews_change_pct)}
          secondHighlight
          color="white"
          trendBadge
        />
      </div>

      <StudentsBar data={cohorts} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 flex-1 min-h-0">
        <RevenueChart data={revenue.months} />
        <SubmissionsChart data={submissions || {}} />
      </div>
    </div>
  );
}
