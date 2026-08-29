import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-primary text-primary-foreground hover:bg-primary/80",
        secondary:
          "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive:
          "border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",
        outline: "text-foreground",
        // Status variants (design-system sweep). Solid `-emphasis` fills pair
        // with `-on-emphasis` ink; the `-subtle` forms are a tinted surface with
        // the ink token on top. No `dark:` variants — the tokens carry the mode.
        success:
          "border-transparent bg-success-emphasis text-success-on-emphasis",
        warning:
          "border-transparent bg-warning-emphasis text-warning-on-emphasis",
        info: "border-transparent bg-info-emphasis text-info-on-emphasis",
        "success-subtle": "border-transparent bg-success-muted text-success",
        "warning-subtle": "border-transparent bg-warning-muted text-warning",
        "info-subtle": "border-transparent bg-info-muted text-info",
        "destructive-subtle":
          "border-transparent bg-destructive-muted text-destructive-ink",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
