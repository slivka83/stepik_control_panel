export function numCell(value, className = '') {
  return (
    <td className={`text-right text-gray-300 font-mono text-xs pl-1 pr-1 ${className}`.trim()}>
      {value}
    </td>
  );
}
