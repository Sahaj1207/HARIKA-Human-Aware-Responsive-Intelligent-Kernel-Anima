import React from 'react';
import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

interface GlassContainerProps extends React.HTMLAttributes<HTMLDivElement> {
  subtle?: boolean;
}

export const GlassContainer: React.FC<GlassContainerProps> = ({
  children,
  className,
  subtle = false,
  ...props
}) => {
  return (
    <div
      className={twMerge(
        clsx(
          'rounded-2xl',
          subtle ? 'surface-translucent-subtle' : 'surface-translucent',
          className
        )
      )}
      {...props}
    >
      {children}
    </div>
  );
};
