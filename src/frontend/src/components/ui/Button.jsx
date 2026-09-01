import React from 'react';
import { Loader2 } from 'lucide-react';

/**
 * Reusable Button primitive supporting multiple visual variants, sizes, and states.
 * 
 * @param {Object} props
 * @param {'primary' | 'secondary' | 'accent' | 'ghost' | 'danger' | 'outline'} [props.variant='secondary']
 * @param {'xs' | 'sm' | 'md' | 'lg'} [props.size='md']
 * @param {React.ReactNode} [props.icon]
 * @param {React.ReactNode} [props.iconRight]
 * @param {boolean} [props.loading=false]
 * @param {boolean} [props.fullWidth=false]
 * @param {string} [props.className='']
 * @param {React.ReactNode} props.children
 */
export default function Button({
  variant = 'secondary',
  size = 'md',
  icon,
  iconRight,
  loading = false,
  fullWidth = false,
  disabled = false,
  className = '',
  children,
  type = 'button',
  ...props
}) {
  const variantClass = `btn-${variant}`;
  const sizeClass = `btn-${size}`;
  const fullWidthClass = fullWidth ? 'btn-full' : '';
  const loadingClass = loading ? 'btn-loading' : '';

  return (
    <button
      type={type}
      disabled={disabled || loading}
      className={`btn-primitive ${variantClass} ${sizeClass} ${fullWidthClass} ${loadingClass} ${className}`.trim()}
      {...props}
    >
      {loading ? (
        <Loader2 size={size === 'xs' ? 12 : size === 'sm' ? 14 : 16} className="animate-spin shrink-0" />
      ) : (
        icon && <span className="btn-icon-left shrink-0">{icon}</span>
      )}
      {children && <span className="btn-label">{children}</span>}
      {!loading && iconRight && <span className="btn-icon-right shrink-0">{iconRight}</span>}
    </button>
  );
}
