export type UserRecord = {
  profile?: {
    email?: string | null;
  } | null;
  fallbackEmail?: string | null;
};

export function displayEmail(user: UserRecord): string {
  // BUG: assumes nested optional profile data is always present.
  const email = user.profile.email.trim().toLowerCase();
  return email || "unknown";
}
