/** Sign-in and registration. Tamil is an unreviewed project translation. */
export const en = {
  "authf.invalid": "Invalid email or password.",
  "authf.minChars": "At least 8 characters.",
  "authf.noAccount": "No account?",
  "authf.haveAccount": "Already registered?",
} as const;

export const ta: Record<keyof typeof en, string> = {
  "authf.invalid": "மின்னஞ்சல் அல்லது கடவுச்சொல் தவறானது.",
  "authf.minChars": "குறைந்தது 8 எழுத்துகள்.",
  "authf.noAccount": "கணக்கு இல்லையா?",
  "authf.haveAccount": "ஏற்கெனவே பதிவு செய்துள்ளீர்களா?",
};

export const auth = { en, ta };
