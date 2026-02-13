import { cn } from "@/lib/utils";

interface LoadingSpinnerProps {
  className?: string;
  size?: "sm" | "md" | "lg";
}

const sizeMap = {
  sm: "size-4 border-2",
  md: "size-8 border-2",
  lg: "size-12 border-3",
} as const;

export function LoadingSpinner({ className, size = "md" }: LoadingSpinnerProps) {
  return (
    <div
      className={cn(
        "animate-spin rounded-full border-muted-foreground/25 border-t-primary",
        sizeMap[size],
        className,
      )}
      role="status"
      aria-label="Loading"
    />
  );
}
