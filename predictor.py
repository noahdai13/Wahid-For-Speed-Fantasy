import tkinter as tk
import requests

sdb = "https://www.thesportsdb.com/api/v1/json/3"

def api_get(endpoint: str, params: dict | None = None) -> dict | None:
    url = f"{sdb}/{endpoint}"
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def search_team(query: str) -> dict | None:
    data = api_get("searchteams.php", {"t": query})
    teams = data.get("teams") if data else None
    return teams[0] if teams else None


def get_team_next_events(team_name: str) -> list:
    team = search_team(team_name)
    if not team:
        return []

    data = api_get("eventsnext.php", {"id": team["idTeam"]})
    return data.get("events", []) if data else []


root = tk.Tk()
root.title("Dark Window")
root.geometry("800x600")
root.configure(bg="#0f1117")

title_label = tk.Label(root, text="Fantasy Points Predictor", fg="white", bg="#0f1117", font=("Helvetica", 24, "bold"))
title_label.pack(pady=20)

search_frame = tk.Frame(root, bg="#0f1117")
search_frame.pack(pady=10)

search_var = tk.StringVar(value="Search fixture:")
search_entry = tk.Entry(search_frame, textvariable=search_var, font=("Helvetica", 14), width=30,
                        fg="#777", bg="#1c1f2a", insertbackground="white", relief="flat", bd=0)
search_entry.pack(side="left")


def on_focus_in(event):
    if search_entry.get() == "Search fixture:":
        search_entry.delete(0, tk.END)
        search_entry.config(fg="white")


def on_focus_out(event):
    if not search_entry.get():
        search_entry.insert(0, "Search fixture:")
        search_entry.config(fg="#777")

def search_enter(event):
    fixtures = get_team_next_events(search_entry.get())
    print(fixtures)


search_entry.bind("<FocusIn>", on_focus_in)
search_entry.bind("<FocusOut>", on_focus_out)
search_entry.bind("<Return>", search_enter)

# Logic



root.mainloop()