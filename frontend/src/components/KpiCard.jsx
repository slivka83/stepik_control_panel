import { memo } from 'react';
import CountUp from 'react-countup';
import PropTypes from 'prop-types';
import { formatNumber } from '../utils/formatNumber';
import { getRatingColor } from '../utils/format';

const COLOR_CLASSES = {
  'cyber-blue': 'text-cyber-blue border-cyber-blue/20',
  'neon-green': 'text-neon-green border-neon-green/20',
  'amber-alert': 'text-amber-alert border-amber-alert/20',
  'crimson-alert': 'text-crimson-alert border-crimson-alert/20',
  white: 'text-gray-300 border-gray-300/20',
  distinction: 'text-[#DB62C4] border-[#DB62C4]/20',
  regular: 'text-[#B70094] border-[#B70094]/20',
};

function KpiCard({
  title,
  value,
  prefix = '',
  suffix = '',
  color = 'cyber-blue',
  trend = null,
  fractionDigits = 0,
  minimumFractionDigits = 0,
  noZero = false,
  secondValue = null,
  secondHighlight = false,
  ratingColor = false,
  trendInverted = false,
  trendTooltip = null,
}) {
  const dp = Math.max(fractionDigits, minimumFractionDigits);
  const fmt = (val) => formatNumber(val, { minimumFractionDigits, maximumFractionDigits: dp });
  const textColor = ratingColor ? undefined : COLOR_CLASSES[color]?.split(' ')[0] || 'text-cyber-blue';
  // `undefined` (KPI not loaded yet) must behave like null: otherwise the card
  // renders arrow + Math.abs(undefined) → "NaN%" before the first response.
  const hasTrend = trend !== null && trend !== undefined;
  const showDash = noZero && (!value || value === 0);

  const getRatingStyle = () => {
    if (!ratingColor) return {};
    return { color: showDash ? '#6b7280' : getRatingColor(value) };
  };

  return (
    <div className="glass-panel glass-panel-hover p-4 transition-all duration-300">
      <div className="flex items-end justify-between mb-2">
        <div className="text-gray-400 text-xs">{title}</div>
        {hasTrend && (
          <span
            title={trendTooltip || undefined}
            className={`text-xs font-mono ${
              trendInverted
                ? trend > 0
                  ? 'text-crimson-alert'
                  : 'text-neon-green'
                : trend >= 0
                  ? 'text-neon-green'
                  : 'text-crimson-alert'
            }`}
          >
            {`${trend >= 0 ? '↑' : '↓'} ${Math.abs(trend)}%`}
          </span>
        )}
      </div>
      <div
        className={`font-mono text-xl lg:text-2xl font-bold whitespace-nowrap ${textColor || ''}`}
        style={getRatingStyle()}
      >
        {prefix}
        {showDash ? (
          <span>—</span>
        ) : (
          <CountUp end={value} duration={1.5} redraw={false} preserveValue decimals={dp} formattingFn={fmt} />
        )}
        {suffix}
        {secondValue !== null && (
          <>
            <span className={`font-mono mx-1 ${secondHighlight ? textColor || '' : '!text-gray-500'}`}>+</span>
            <span className={secondHighlight ? textColor || '' : '!text-gray-500'}>
              <CountUp
                end={secondValue}
                duration={1.5}
                redraw={false}
                preserveValue
                decimals={dp}
                formattingFn={fmt}
              />
            </span>
          </>
        )}
      </div>
    </div>
  );
}

export default memo(KpiCard);

KpiCard.propTypes = {
  title: PropTypes.string.isRequired,
  value: PropTypes.number.isRequired,
  prefix: PropTypes.string,
  suffix: PropTypes.string,
  color: PropTypes.oneOf([
    'cyber-blue',
    'neon-green',
    'amber-alert',
    'crimson-alert',
    'white',
    'distinction',
    'regular',
  ]),
  trend: PropTypes.number,
  trendInverted: PropTypes.bool,
  trendTooltip: PropTypes.string,
  fractionDigits: PropTypes.number,
  secondValue: PropTypes.number,
  secondHighlight: PropTypes.bool,
};
