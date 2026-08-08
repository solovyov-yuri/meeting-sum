import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef } from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 disabled:pointer-events-none disabled:opacity-[0.48]",
  {
    variants: {
      variant: {
        primary: "bg-accent text-white hover:bg-accent-hover",
        secondary: "bg-panel text-ink border border-border hover:bg-app",
        ghost: "text-ink-muted hover:bg-app hover:text-ink",
        danger: "bg-danger text-white hover:bg-danger/90",
        subtle: "bg-accent-soft text-accent hover:bg-accent/15",
      },
      size: {
        sm: "h-[30px] px-2.5 text-base",
        md: "h-[34px] px-3 text-base",
        lg: "h-[34px] px-3.5 text-base",
        icon: "h-[34px] w-[34px]",
      },
    },
    defaultVariants: { variant: "secondary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
  ),
);
Button.displayName = "Button";
