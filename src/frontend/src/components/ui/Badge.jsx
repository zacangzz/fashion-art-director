import React from 'react';
import { X } from 'lucide-react';

/**
 * Reusable Badge primitive for tags, statuses, and counters.
 * 
 * @param {Object} props
 * @param {'primary' | 'success' | 'warning' | 'danger' | 'cyan' | 'purple' | 'neutral'} [props.variant='neutral']
 * @param {'xs' | 'sm' | 'md'} [props.size='sm']
 * @param {boolean} [props.dot=false]
 * @param {React.ReactNode} [props.icon]
 * @param {Function} [props.onDismiss]
 * @param {string} [props.className='']
 * @param {React.ReactNode} props.children
 */
export default function Badge({
  variant = 'neutral',
  size = 'sm',
  dot = false,
  icon,
  onDismiss,
  className = '',
  children,
  ...props
}) {
  return (
    <span
      className={`badge-primitive badge-${variant} badge-${size} ${className}`.trim()}
      {...props}
    >
      {dot && <span className="badge-dot" />}
      {icon && <span className="badge-icon">{icon}</span>}
      {children && <span className="badge-label">{children}</span>}
      {onDismiss && (
        <button
          type="button"
          className="badge-dismiss-btn"
          onClick={(e) => {
            e.stopPropagation();
            onDismiss();
          }}
          aria-label="Remove badge"
        >
          <X size={11} />
        </button>
      )}
    </span>
  );
}
