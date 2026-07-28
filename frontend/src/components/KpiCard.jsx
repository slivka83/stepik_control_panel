import { memo } from 'react'
import CountUp from 'react-countup'
import PropTypes from 'prop-types'
import { formatNumber } from '../utils/formatNumber'

const COLOR_CLASSES = {
  'cyber-blue': 'text-cyber-blue border-cyber-blue/20',
  'neon-green': 'text-neon-green border-neon-green/20',
  'amber-alert': 'text-amber-alert border-amber-alert/20',
  'crimson-alert': 'text-crimson-alert border-crimson-alert/20',
  'white': 'text-gray-300 border-gray-300/20',
  'dim-green': 'text-[#22763d] border-[#22763d]/20',
  'dim-blue': 'text-[#1a6a9e] border-[#1a6a9e]/20',
  'dim-crimson': 'text-[#8b2040] border-[#8b2040]/20',
}

function KpiCard({ title, value, prefix = '', suffix = '', color = 'cyber-blue', trend = null, fractionDigits = 0, minimumFractionDigits = 0, noAnimate = false, secondValue = null, secondSuffix = '', ratingColor = false }) {
  const dp = Math.max(fractionDigits, minimumFractionDigits)
  const fmt = (val) => formatNumber(val, { minimumFractionDigits, maximumFractionDigits: fractionDigits })
  const textColor = ratingColor
    ? undefined
    : COLOR_CLASSES[color]?.split(' ')[0] || 'text-cyber-blue'

  const getRatingStyle = () => {
    if (!ratingColor) return {}
    const r = Math.max(1, Math.min(5, value))
    const stops = [
      [1.0, 239, 68, 68],
      [2.0, 249, 115, 22],
      [3.0, 234, 179, 8],
      [4.0, 132, 204, 22],
      [4.5, 100, 214, 81],
      [4.9, 74, 222, 128],
    ]
    let i = 0
    while (i < stops.length - 1 && stops[i + 1][0] < r) i++
    if (i >= stops.length - 1) {
      const [, cr, cg, cb] = stops[stops.length - 1]
      return { color: `rgb(${cr}, ${cg}, ${cb})` }
    }
    const [r0, r1, g1, b1] = stops[i]
    const [r1v, r2, g2, b2] = stops[i + 1]
    const t = (r - r0) / (r1v - r0)
    return { color: `rgb(${Math.round(r1 + (r2 - r1) * t)}, ${Math.round(g1 + (g2 - g1) * t)}, ${Math.round(b1 + (b2 - b1) * t)})` }
  }

  return (
    <div className="glass-panel glass-panel-hover p-4 transition-all duration-300">
      <div className="flex items-end justify-between mb-2">
        <div className="text-gray-400 text-xs">{title}</div>
        {trend !== null && (
          <span className={`text-xs font-mono ${trend >= 0 ? 'text-neon-green' : 'text-crimson-alert'}`}>
            {trend >= 0 ? '↑' : '↓'} {Math.abs(trend)}%
          </span>
        )}
      </div>
      <div className={`font-mono text-xl lg:text-2xl font-bold whitespace-nowrap ${textColor || ''}`} style={getRatingStyle()}>
        {prefix}
        {noAnimate ? (
          <span>{fmt(value)}</span>
        ) : (
          <CountUp
            end={value}
            duration={1.5}
            redraw={false}
            preserveValue
            decimals={dp}
            formattingFn={fmt}
          />
        )}
        {suffix}
        {secondValue !== null && (
          <>
            <span className="!text-gray-500 font-mono mx-1">+</span>
            <span className="!text-gray-500">
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
            <span className="!text-gray-500">{secondSuffix}</span>
          </>
        )}
      </div>
    </div>
  )
}

export default memo(KpiCard)

KpiCard.propTypes = {
  title: PropTypes.string.isRequired,
  value: PropTypes.number.isRequired,
  prefix: PropTypes.string,
  suffix: PropTypes.string,
  color: PropTypes.oneOf(['cyber-blue', 'neon-green', 'amber-alert', 'crimson-alert', 'white', 'dim-green', 'dim-blue', 'dim-crimson']),
  trend: PropTypes.number,
  fractionDigits: PropTypes.number,
  secondValue: PropTypes.number,
  secondSuffix: PropTypes.string,
}
