import React from 'react';

/**
 * Reusable Card container primitive with glassmorphism and elevated variants.
 * 
 * @param {Object} props
 * @param {'default' | 'elevated' | 'bordered' | 'interactive' | 'accent-glow'} [props.variant='default']
 * @param {React.ReactNode} [props.title]
 * @param {React.ReactNode} [props.subtitle]
 * @param {React.ReactNode} [props.icon]
 * @param {React.ReactNode} [props.badge]
 * @param {React.ReactNode} [props.actions]
 * @param {React.ReactNode} [props.footer]
 * @param {string} [props.className='']
 * @param {React.ReactNode} props.children
 */
export default function Card({
  variant = 'default',
  title,
  subtitle,
  icon,
  badge,
  actions,
  footer,
  className = '',
  children,
  ...props
}) {
  const hasHeader = title || subtitle || icon || badge || actions;

  return (
    <div className={`card-primitive card-${variant} ${className}`.trim()} {...props}>
      {hasHeader && (
        <div className="card-header-primitive">
          <div className="card-header-left">
            {icon && <span className="card-header-icon">{icon}</span>}
            <div>
              {title && <h4 className="card-title-primitive">{title}</h4>}
              {subtitle && <p className="card-subtitle-primitive">{subtitle}</p>}
            </div>
            {badge && <div className="card-header-badge">{badge}</div>}
          </div>
          {actions && <div className="card-header-actions">{actions}</div>}
        </div>
      )}

      <div className="card-body-primitive">{children}</div>

      {footer && <div className="card-footer-primitive">{footer}</div>}
    </div>
  );
}
