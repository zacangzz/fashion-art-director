import React from 'react';
import { ChevronDown } from 'lucide-react';

/**
 * Reusable Select dropdown primitive with custom arrow adornment and error state.
 * 
 * @param {Object} props
 * @param {string} [props.label]
 * @param {string} [props.hint]
 * @param {string} [props.error]
 * @param {React.ReactNode} [props.icon]
 * @param {Array<{value: string|number, label: string}|string>} props.options
 * @param {'sm' | 'md' | 'lg'} [props.size='md']
 * @param {string} [props.className='']
 */
export default function Select({
  label,
  hint,
  error,
  icon,
  options = [],
  size = 'md',
  className = '',
  disabled = false,
  id,
  value,
  onChange,
  ...props
}) {
  const selectId = id || (label ? `select-${label.toLowerCase().replace(/\s+/g, '-')}` : undefined);

  return (
    <div className={`select-wrapper select-${size} ${disabled ? 'select-disabled' : ''} ${error ? 'select-error' : ''} ${className}`.trim()}>
      {label && (
        <label htmlFor={selectId} className="select-label">
          {label}
        </label>
      )}

      <div className="select-input-container">
        {icon && <span className="select-left-icon">{icon}</span>}
        <select
          id={selectId}
          disabled={disabled}
          value={value}
          onChange={onChange}
          className="select-input"
          {...props}
        >
          {options.map((opt) => {
            const isObj = typeof opt === 'object' && opt !== null;
            const val = isObj ? opt.value : opt;
            const text = isObj ? opt.label : opt;
            return (
              <option key={val} value={val}>
                {text}
              </option>
            );
          })}
        </select>
        <ChevronDown size={14} className="select-chevron" />
      </div>

      {error && <span className="select-error-text">{error}</span>}
      {hint && !error && <span className="select-hint-text">{hint}</span>}
    </div>
  );
}
