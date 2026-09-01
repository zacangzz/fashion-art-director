import React from 'react';

/**
 * Reusable Range Slider primitive with live value display badge and step markers.
 * 
 * @param {Object} props
 * @param {string} [props.label]
 * @param {number} props.value
 * @param {Function} props.onChange
 * @param {number} [props.min=0]
 * @param {number} [props.max=100]
 * @param {number} [props.step=1]
 * @param {Function} [props.formatValue]
 * @param {string} [props.hint]
 * @param {string} [props.className='']
 */
export default function Slider({
  label,
  value,
  onChange,
  min = 0,
  max = 100,
  step = 1,
  formatValue,
  hint,
  disabled = false,
  className = '',
  ...props
}) {
  const displayValue = formatValue ? formatValue(value) : value;

  return (
    <div className={`slider-wrapper ${disabled ? 'slider-disabled' : ''} ${className}`.trim()}>
      <div className="slider-header">
        {label && <span className="slider-label">{label}</span>}
        <span className="slider-value-badge">{displayValue}</span>
      </div>

      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange?.(Number(e.target.value))}
        className="slider-input"
        {...props}
      />

      {hint && <span className="slider-hint">{hint}</span>}
    </div>
  );
}
