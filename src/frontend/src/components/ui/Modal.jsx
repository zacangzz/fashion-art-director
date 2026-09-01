import React, { useEffect } from 'react';
import { X } from 'lucide-react';

/**
 * Accessible Modal dialog primitive with backdrop blur, Esc key dismissal, and body scroll lock.
 * 
 * @param {Object} props
 * @param {boolean} props.isOpen
 * @param {Function} props.onClose
 * @param {React.ReactNode} [props.title]
 * @param {React.ReactNode} [props.subtitle]
 * @param {React.ReactNode} [props.icon]
 * @param {'sm' | 'md' | 'lg' | 'xl' | 'full'} [props.size='md']
 * @param {boolean} [props.showCloseButton=true]
 * @param {boolean} [props.closeOnBackdrop=true]
 * @param {React.ReactNode} [props.footer]
 * @param {string} [props.className='']
 * @param {React.ReactNode} props.children
 */
export default function Modal({
  isOpen,
  onClose,
  title,
  subtitle,
  icon,
  size = 'md',
  showCloseButton = true,
  closeOnBackdrop = true,
  footer,
  className = '',
  children,
  ...props
}) {
  useEffect(() => {
    if (!isOpen) return;

    // Esc key handler
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose?.();
      }
    };

    // Body scroll lock
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleBackdropClick = (e) => {
    if (closeOnBackdrop && e.target === e.currentTarget) {
      onClose?.();
    }
  };

  return (
    <div
      className="modal-overlay"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby={title ? 'modal-title' : undefined}
      {...props}
    >
      <div className={`modal-container modal-${size} ${className}`.trim()}>
        {(title || showCloseButton) && (
          <div className="modal-header">
            <div className="modal-header-text">
              {icon && <span className="modal-header-icon">{icon}</span>}
              <div>
                {title && <h3 id="modal-title" className="modal-title">{title}</h3>}
                {subtitle && <p className="modal-subtitle">{subtitle}</p>}
              </div>
            </div>
            {showCloseButton && (
              <button
                type="button"
                className="modal-close-btn"
                onClick={onClose}
                aria-label="Close dialog"
              >
                <X size={18} />
              </button>
            )}
          </div>
        )}

        <div className="modal-body">{children}</div>

        {footer && <div className="modal-footer">{footer}</div>}
      </div>
    </div>
  );
}
