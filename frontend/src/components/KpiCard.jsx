import CountUp from 'react-countup'

export default function KpiCard({ title, value, prefix = '', suffix = '', color = 'cyber-blue', trend = null }) {
  const colorClasses = {
    'cyber-blue': 'text-cyber-blue border-cyber-blue/20',
    'neon-green': 'text-neon-green border-neon-green/20',
    'amber-alert': 'text-amber-alert border-amber-alert/20',
    'crimson-alert': 'text-crimson-alert border-crimson-alert/20',
  }

  return (
    <div className={`glass-panel glass-panel-hover p-5 transition-all duration-300`}>
      <div className="text-gray-400 text-sm mb-2">{title}</div>
      <div className={`font-mono text-2xl lg:text-3xl font-bold ${colorClasses[color]?.split(' ')[0] || 'text-cyber-blue'}`}>
        {prefix}
        <CountUp end={value} duration={1.5} separator=" " />
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
