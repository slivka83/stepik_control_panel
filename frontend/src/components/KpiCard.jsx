import CountUp from 'react-countup'
import PropTypes from 'prop-types'
import { formatNumber } from '../utils/formatNumber'

const COLOR_CLASSES = {
  'cyber-blue': 'text-cyber-blue border-cyber-blue/20',
  'neon-green': 'text-neon-green border-neon-green/20',
  'amber-alert': 'text-amber-alert border-amber-alert/20',
  'crimson-alert': 'text-crimson-alert border-crimson-alert/20',
}

export default function KpiCard({ title, value, prefix = '', suffix = '', color = 'cyber-blue', trend = null }) {
  const textColor = COLOR_CLASSES[color]?.split(' ')[0] || 'text-cyber-blue'

  return (
    <div className="glass-panel glass-panel-hover p-4 transition-all duration-300">
      <div className="text-gray-400 text-xs mb-2">{title}</div>
      <div className={`font-mono text-xl lg:text-2xl font-bold whitespace-nowrap ${textColor}`}>
        {prefix}
        <CountUp
          end={value}
          duration={1.5}
          redraw={false}
          preserveValue
          formattingFn={(val) => formatNumber(val)}
        />
        {suffix}
      </div>
      {trend !== null && (
        <div className={`mt-2 text-xs font-mono ${trend >= 0 ? 'text-neon-green' : 'text-crimson-alert'}`}>
          {trend >= 0 ? '↑' : '↓'} {Math.abs(trend)}%
        </div>
      )}
    </div>
  )
}

KpiCard.propTypes = {
  title: PropTypes.string.isRequired,
  value: PropTypes.number.isRequired,
  prefix: PropTypes.string,
  suffix: PropTypes.string,
  color: PropTypes.oneOf(['cyber-blue', 'neon-green', 'amber-alert', 'crimson-alert']),
  trend: PropTypes.number,
}
