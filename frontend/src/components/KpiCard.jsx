import { memo } from 'react';
import CountUp from 'react-countup';
import PropTypes from 'prop-types';
import { formatNumber } from '../utils/formatNumber';

const COLOR_CLASSES = {
  'cyber-blue': 'text-cyber-blue border-cyber-blue/20',
  'neon-green': 'text-neon-green border-neon-green/20',
  'amber-alert': 'text-amber-alert border-amber-alert/20',
  'crimson-alert': 'text-crimson-alert border-crimson-alert/20',
  white: 'text-gray-300 border-gray-300/20',
  'dim-green': 'text-[#22763d] border-[#22763d]/20',
  'dim-blue': 'text-[#1a6a9e] border-[#1a6a9e]/20',
  'dim-crimson': 'text-[#8b2040] border-[#8b2040]/20',
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
  noAnimate = false,
  secondValue = null,
  secondSuffix = '',
  secondHighlight = false,
  ratingColor = false,
  trendInverted = false,
  trendTooltip = null,
}) {
  const dp = Math.max(fractionDigits, minimumFractionDigits);
  const fmt = (val) => formatNumber(val, { minimumFractionDigits, maximumFractionDigits: fractionDigits });
  const textColor = ratingColor ? undefined : COLOR_CLASSES[color]?.split(' ')[0] || 'text-cyber-blue';

  const getRatingStyle = () => {
    if (!ratingColor) return {};
    const r = value == null ? 0 : Math.max(1, Math.min(5, value));
    const stops = [
      [1.0, 255, 0, 0],
      [2.0, 255, 120, 0],
      [3.0, 255, 210, 0],
      [4.0, 160, 230, 0],
      [4.5, 0, 180, 0],
      [4.9, 0, 255, 0],
    ];
    let color = stops[0];
    for (const [stop, cr, cg, cb] of stops) {
      if (r >= stop) color = [cr, cg, cb];
      else break;
    }
    const [cr, cg, cb] = color;
    return { color: `rgb(${cr}, ${cg}, ${cb})` };
  };

  return (
    <div className="glass-panel glass-panel-hover p-4 transition-all duration-300">
      <div className="flex items-end justify-between mb-2">
        <div className="text-gray-400 text-xs">{title}</div>
        {trend !== null && (
          <span
            title={trendTooltip || undefined}
            className={`text-xs font-mono ${trendInverted ? (trend > 0 ? 'text-crimson-alert' : 'text-neon-green') : trend > 0 ? 'text-neon-green' : 'text-crimson-alert'}`}
          >
            {trend >= 0 ? '↑' : '↓'} {Math.abs(trend)}%
          </span>
        )}
      </div>
      <div
        className={`font-mono text-xl lg:text-2xl font-bold whitespace-nowrap ${textColor || ''}`}
        style={getRatingStyle()}
      >
        {prefix}
        {noAnimate ? (
          <span>{fmt(value)}</span>
        ) : (
          <CountUp end={value} duration={1.5} redraw={false} preserveValue decimals={dp} formattingFn={fmt} />
        )}
        {suffix}
        {secondValue !== null && (
          <>
            <span className={`font-mono mx-1 ${secondHighlight ? textColor || '' : '!text-gray-500'}`}>+</span>
            <span className={secondHighlight ? textColor || '' : '!text-gray-500'}>
              {noAnimate ? (
                <span>{fmt(secondValue)}</span>
              ) : (
                <CountUp
                  end={secondValue}
                  duration={1.5}
                  redraw={false}
                  preserveValue
                  decimals={dp}
                  formattingFn={fmt}
                />
              )}
            </span>
            <span className={`${secondHighlight ? textColor || '' : '!text-gray-500'}`}>{secondSuffix}</span>
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
    'dim-green',
    'dim-blue',
    'dim-crimson',
    'distinction',
    'regular',
  ]),
  trend: PropTypes.number,
  trendInverted: PropTypes.bool,
  trendTooltip: PropTypes.string,
  fractionDigits: PropTypes.number,
  secondValue: PropTypes.number,
  secondSuffix: PropTypes.string,
  secondHighlight: PropTypes.bool,
};
