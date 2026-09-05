"""LYA KALI SKILL — teaches you the ethical hacker's operating system.
Safe by design: LYA explains Kali, its tools, its philosophy, and quizzes you.
She never runs attacks — that stays in hacker.py with its ownership gate.

Say things like:
  "kali about"          — what Kali Linux is
  "kali roadmap"        — full learning roadmap for ethical hacking
  "kali lesson 1..12"   — short lessons
  "kali command nmap"   — info about a famous Kali tool
  "kali tools"          — list the top tools
  "kali quiz"           — quiz question
"""
import random

# ---------------- LESSONS ----------------
LESSONS = {
    1: ("What is Kali Linux?",
        "Kali Linux is a Debian-based OS made by OffSec, built for penetration "
        "testing and digital forensics. It ships with 300+ security tools "
        "pre-installed. Golden rule: use it ONLY on systems you own or have "
        "written permission to test. That rule is what separates an ethical "
        "hacker from a criminal."),
    2: ("The Linux terminal",
        "The terminal is the heart of Linux. Key commands: ls (list files), "
        "cd (change directory), pwd (where am I), cat (read a file), man "
        "(read a command's manual). In Kali, almost everything is done in the "
        "terminal — learn 'man <command>' first; it's the manual for everything."),
    3: ("Users, roots and permissions",
        "Linux has users and groups. 'root' is the superuser. sudo lets an "
        "ordinary user run a command as root. File permissions are read/write/"
        "execute for user/group/others — chmod changes them. Weak permissions "
        "are one of the most common ways systems get owned."),
    4: ("Networking basics",
        "Every machine has an IP address. Ports are numbered doors: 22=SSH, "
        "80=HTTP, 443=HTTPS, 445=SMB. Tools: ip a (show your IPs), ping (is a "
        "host alive), netstat (what connections exist). If you don't understand "
        "networking, you can't understand hacking."),
    5: ("Recon — the first phase of any pentest",
        "Before touching anything, a pentester gathers info: whois (who owns a "
        "domain), theHarvester (emails and subdomains), whatweb (what a site "
        "runs). Recon is 100% passive and legal when done on public data. "
        "Professional pentesters spend more time here than on attacks."),
    6: ("Scanning with Nmap",
        "nmap maps a network: 'nmap -sV target' finds open ports and service "
        "versions. It is the single most famous security tool. Rule: scan only "
        "your own lab machines. LYA has a built-in pure-Python port scanner — "
        "say 'scan my ports' and she'll show you how it works on localhost."),
    7: ("Vulnerabilities",
        "A vulnerability is a weakness; an exploit is code that uses it. CVE "
        "IDs (like CVE-2021-44228, Log4Shell) name them publicly. Search "
        "exploitdb.com to read real advisories. Study HOW a bug works — that "
        "knowledge is what makes you valuable, not the exploit itself."),
    8: ("Web application attacks (in a lab)",
        "Most real hacking is web. Learn: HTTP methods, cookies, sessions, "
        "SQL injection, XSS. Practice ONLY in legal labs: DVWA, bWAPP, "
        "PortSwigger Web Security Academy (free!), HackTheBox, TryHackMe. "
        "Never test a website you don't own — that's a crime in India under "
        "the IT Act 2000, Sec 43/66."),
    9: ("Passwords and hashes",
        "Systems store password HASHES, not passwords. Tools like hashcat and "
        "John the Ripper test hashes against wordlists (rockyou.txt). "
        "LYA can audit password strength — say 'how strong is my password'. "
        "Lesson: length beats complexity; passphrases win."),
    10: ("Wireless security",
         "WiFi uses WPA2/WPA3. Attacks like capturing handshakes and cracking "
         "them need a monitor-mode adapter and a network you OWN. airmon-ng, "
         "airodump-ng, aircrack-ng are the classic suite. Never touch a "
         "neighbour's WiFi — that's illegal everywhere."),
    11: ("Metasploit — the framework",
         "Metasploit organizes exploits, payloads and listeners. msfconsole is "
         "its shell. In a lab you'll learn: choose exploit, set target, run, "
         "get a session. Understanding it teaches you how defenders must think. "
         "Use it against Metasploitable (a VM made to be attacked)."),
    12: ("Reporting — what makes a professional",
         "A pentest ends with a report: what you found, how severe it is, how "
         "to fix it. Companies pay for FIXES, not for break-ins. If you can "
         "write a clear report and explain the fix, you're employable. "
         "Certifications to aim for: CEH, eJPT, OSCP."),
}

ROADMAP = [
    "1. Linux fundamentals — spend 2 weeks in the terminal (overthewire.org Bandit, free)",
    "2. Networking — TCP/IP, ports, DNS, HTTP (try 'kali lesson 4')",
    "3. Python scripting — you're already doing this with LYA!",
    "4. Legal practice labs — TryHackMe (beginner) then HackTheBox (free tiers)",
    "5. Web security — PortSwigger Web Security Academy (completely free)",
    "6. Tooling — nmap, Burp Suite, Metasploit, Wireshark in your own VM lab",
    "7. Certifications — eJPT (easy entry) → CEH (HR filter) → OSCP (gold standard)",
    "8. Specialise — web app, network, cloud, or mobile security",
]

TOOLS = {
    "nmap": ("Network scanner. Finds live hosts, open ports, service versions. "
             "Example: nmap -sV -p 1-1000 192.168.1.10 — your lab only."),
    "wireshark": ("Packet sniffer. Captures and inspects network traffic "
                  "packet-by-packet. Great for learning how protocols really work."),
    "metasploit": ("Exploitation framework (msfconsole). Matches exploits to "
                   "vulnerable targets in your lab. Learn it on Metasploitable VM."),
    "burpsuite": ("Web proxy. Sits between your browser and a site so you can "
                  "inspect/modify requests. The #1 web-hacking tool."),
    "aircrack-ng": ("WiFi security suite: capture handshakes, crack WPA keys "
                    "from wordlists. Own network only."),
    "john": ("John the Ripper — password hash cracker. Teaches you why weak "
             "passwords die in seconds."),
    "hydra": ("Login brute-forcer (SSH, FTP, web forms). Use against your own "
              "lab services to see why rate-limiting matters."),
    "sqlmap": ("Automates SQL injection discovery — against test apps like DVWA, "
               "never a live site."),
    "nikto": ("Web server scanner for known misconfigurations and outdated "
              "software. Safe-ish for your own sites."),
    "netcat": ("The 'TCP swiss army knife' — raw connections, banners, "
               "simple listeners. Every hacker's first tool."),
    "gobuster": ("Directory/file brute-forcer for websites. Finds hidden admin "
                 "pages on your own test server."),
    "tcpdump": ("Command-line packet capture. Wireshark's terminal cousin."),
    "whois": ("Looks up domain registration info. Passive recon, fully legal."),
    "hashcat": ("GPU-powered password cracker. Runs on Windows too — LYA could "
                "show you benchmarks on your own machine."),
    "searchsploit": ("Offline search of the Exploit-DB database. Read "
                     "advisories to learn, not to attack."),
    "maltego": ("OSINT and link-analysis: maps people, domains and companies "
                "into graphs. Passive recon."),
    "chntpw": ("Resets Windows passwords from a boot USB — great for "
               "understanding why full-disk encryption matters."),
    "volatility": ("Memory forensics: analyses RAM dumps. Forensics career path."),
}

QUIZ = [
    ("Which Kali tool maps open ports and service versions?", "nmap"),
    ("What does 'sudo' do?", "runs a command as root / superuser"),
    ("Port 443 is usually what protocol?", "https"),
    ("What is a CVE?", "a public ID for a known vulnerability"),
    ("Name the web proxy tool in Kali used for testing web apps.", "burpsuite"),
    ("What law (India) makes unauthorised hacking a crime?", "IT Act 2000"),
    ("Which suite cracks WiFi WPA handshakes?", "aircrack-ng"),
    ("What stores passwords on Linux — plaintext or hashes?", "hashes"),
    ("Which database lists known public exploits?", "exploit-db / exploitdb"),
    ("What should ALWAYS exist before you test someone else's system?", "written permission"),
]

# ---------------- HELPERS ----------------
def _menu():
    return ("Kali skill ready. Try: 'kali about', 'kali roadmap', 'kali lesson 1', "
            "'kali command nmap', 'kali tools', 'kali quiz'.")

def _quiz():
    q, a = random.choice(QUIZ)
    return f"QUIZ: {q}\n(Answer: {a})"

# ---------------- MAIN API ----------------
def about():
    return LESSONS[1][1]

def roadmap():
    return ("Your ethical-hacker roadmap, in order:\n" + "\n".join(ROADMAP)
            + "\n\nStart tonight with step 1. LYA tracks your progress.")

def lesson(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return f"Lesson number please. I have lessons 1–12. {_menu()}"
    if n not in LESSONS:
        return f"I have lessons 1–12. {_menu()}"
    title, body = LESSONS[n]
    return f"Lesson {n}: {title}\n{body}"

def cmd_info(name):
    name = (name or "").strip().lower()
    if name in TOOLS:
        return f"{name}: {TOOLS[name]}"
    close = [t for t in TOOLS if name and (name in t or t in name)]
    if close:
        return "Did you mean: " + ", ".join(sorted(close)[:5]) + "?"
    return (f"I don't have '{name}' in my tool book yet. Top ones I know: "
            + ", ".join(list(TOOLS)[:8]) + ".")

def match(text):
    t = text.lower()
    return t.startswith("kali") or "kali linux" in t

def reply(text, say, ask):
    t = text.lower().strip()
    if "roadmap" in t or "path" in t or "plan" in t:
        return roadmap()
    if "quiz" in t or "test me" in t:
        return _quiz()
    if "about" in t or "what is kali" in t:
        return about()
    if "tool" in t:
        return ("Top Kali tools I know: " + ", ".join(TOOLS)
                + ".\nAsk 'kali command <name>' for details.")
    if "lesson" in t:
        num = "".join(ch for ch in t if ch.isdigit()) or ""
        if not num:
            return ("Lessons: " + "; ".join(f"{n}. {LESSONS[n][0]}" for n in LESSONS)
                    + "\nSay 'kali lesson 3' to read one.")
        return lesson(num)
    if "command" in t or "cmd" in t:
        name = t.split("command", 1)[-1].split("cmd", 1)[-1].strip(" ?.")
        return cmd_info(name)
    return _menu()
