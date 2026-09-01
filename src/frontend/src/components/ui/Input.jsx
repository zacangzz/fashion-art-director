import React from 'react';

/**
 * Reusable Input / Textarea primitive with focus rings, icons, and error handling.
 * 
 * @param {Object} props
 * @param {string} [props.label]
 * @param {string} [props.hint]
 * @param {string} [props.error]
 * @param {React.ReactNode} [props.icon]
 * @param {React.ReactNode} [props.iconRight]
 * @param {boolean} [props.multiline=false]
 * @param {number} [props.rows=3]
 * @param {'sm' | 'md' | 'lg'} [props.size='md']
 * @param {string} [props.className='']
 */
export default function Input({
  label,
  hint,
  error,
  icon,
  iconRight,
  multiline = false,
  rows = 3,
  size = 'md',
  className = '',
  disabled = false,
  id,
  type = 'text',
  value,
  onChange,
  ...props
}) {
  const inputId = id || (label ? `input-${label.toLowerCase().replace(/\s+/g, '-')}` : undefined);

  return (
    <div className={`input-wrapper input-${size} ${disabled ? 'input-disabled' : ''} ${error ? 'input-error' : ''} ${className}`.trim()}>
      {label && (
        <label htmlFor={inputId} className="input-label">
          {label}
        </label>
      )}

      <div className="input-field-container">
        {icon && <span className="input-left-icon">{icon}</span>}
        {multiline ? (
          <textarea
            id={inputId}
            disabled={disabled}
            rows={rows}
            value={value}
            onChange={onChange}
            className="input-field input-textarea"
            {...props}
          />
        ) : (
          <input
            id={inputId}
            type={type}
            disabled={disabled}
            value={value}
            onChange={onChange}
            className="input-field"
            {...props}
          />
        )}
        {iconRight && <span className="input-right-icon">{iconRight}</span>}
      </div>

      {error && <span className="input-error-text">{error}</span>}
      {hint && !error && <span className="input-hint-text">{hint}</span>}
    </div>
  );
}
