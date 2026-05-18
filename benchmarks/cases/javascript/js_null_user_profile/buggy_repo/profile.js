function getDisplayName(user) {
  // BUG: assumes every user has a profile object with a string name.
  const name = user.profile.name.trim();
  return name || "Guest";
}

module.exports = { getDisplayName };
