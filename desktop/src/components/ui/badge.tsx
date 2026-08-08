import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-sm font-medium leading-none",
  {
    variants: {
      tone: {
        neutral: "bg-app text-ink-muted",
        accent: "bg-accent-soft text-accent",
        ok: "bg-green-50 text-ok",
        warn: "bg-amber-50 text-warn",
        danger: "bg-red-50 text-danger",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
