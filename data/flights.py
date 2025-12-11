# flights.py - Mock flight data for demo
# Includes routes from major Indian cities to popular international destinations

FLIGHTS = [
    # Bangalore (BLR) to Dubai (DXB) - Multiple dates in April 2026
    {"id": "F001", "from": "BLR", "to": "DXB", "date": "2026-04-01", "price": 350, "airline": "Emirates", "departure": "06:00", "arrival": "08:30", "duration": "4h 30m"},
    {"id": "F002", "from": "BLR", "to": "DXB", "date": "2026-04-01", "price": 280, "airline": "IndiGo", "departure": "10:30", "arrival": "13:00", "duration": "4h 30m"},
    {"id": "F003", "from": "BLR", "to": "DXB", "date": "2026-04-05", "price": 320, "airline": "Air India", "departure": "14:00", "arrival": "16:30", "duration": "4h 30m"},
    {"id": "F004", "from": "BLR", "to": "DXB", "date": "2026-04-10", "price": 290, "airline": "SpiceJet", "departure": "08:00", "arrival": "10:30", "duration": "4h 30m"},
    {"id": "F005", "from": "BLR", "to": "DXB", "date": "2026-04-15", "price": 380, "airline": "Emirates", "departure": "22:00", "arrival": "00:30", "duration": "4h 30m"},
    {"id": "F006", "from": "BLR", "to": "DXB", "date": "2026-04-20", "price": 310, "airline": "Etihad", "departure": "11:00", "arrival": "13:30", "duration": "4h 30m"},
    
    # Return flights: Dubai (DXB) to Bangalore (BLR)
    {"id": "F007", "from": "DXB", "to": "BLR", "date": "2026-04-06", "price": 340, "airline": "Emirates", "departure": "09:00", "arrival": "14:30", "duration": "4h 30m"},
    {"id": "F008", "from": "DXB", "to": "BLR", "date": "2026-04-06", "price": 260, "airline": "IndiGo", "departure": "15:00", "arrival": "20:30", "duration": "4h 30m"},
    {"id": "F009", "from": "DXB", "to": "BLR", "date": "2026-04-10", "price": 300, "airline": "Air India", "departure": "18:00", "arrival": "23:30", "duration": "4h 30m"},
    {"id": "F010", "from": "DXB", "to": "BLR", "date": "2026-04-15", "price": 275, "airline": "SpiceJet", "departure": "07:00", "arrival": "12:30", "duration": "4h 30m"},
    {"id": "F011", "from": "DXB", "to": "BLR", "date": "2026-04-20", "price": 365, "airline": "Emirates", "departure": "23:00", "arrival": "04:30", "duration": "4h 30m"},
    {"id": "F012", "from": "DXB", "to": "BLR", "date": "2026-04-25", "price": 295, "airline": "Etihad", "departure": "12:00", "arrival": "17:30", "duration": "4h 30m"},
    
    # Delhi (DEL) to Dubai (DXB)
    {"id": "F013", "from": "DEL", "to": "DXB", "date": "2026-04-01", "price": 320, "airline": "Emirates", "departure": "07:00", "arrival": "09:00", "duration": "3h 30m"},
    {"id": "F014", "from": "DEL", "to": "DXB", "date": "2026-04-05", "price": 250, "airline": "IndiGo", "departure": "13:00", "arrival": "15:00", "duration": "3h 30m"},
    {"id": "F015", "from": "DEL", "to": "DXB", "date": "2026-04-10", "price": 280, "airline": "Air India", "departure": "20:00", "arrival": "22:00", "duration": "3h 30m"},
    
    # Mumbai (BOM) to Dubai (DXB)
    {"id": "F016", "from": "BOM", "to": "DXB", "date": "2026-04-01", "price": 300, "airline": "Emirates", "departure": "08:00", "arrival": "09:30", "duration": "3h"},
    {"id": "F017", "from": "BOM", "to": "DXB", "date": "2026-04-05", "price": 240, "airline": "IndiGo", "departure": "14:00", "arrival": "15:30", "duration": "3h"},
    {"id": "F018", "from": "BOM", "to": "DXB", "date": "2026-04-10", "price": 270, "airline": "SpiceJet", "departure": "21:00", "arrival": "22:30", "duration": "3h"},
    
    # Chennai (MAA) to Dubai (DXB)
    {"id": "F019", "from": "MAA", "to": "DXB", "date": "2026-04-01", "price": 330, "airline": "Emirates", "departure": "06:30", "arrival": "09:00", "duration": "4h"},
    {"id": "F020", "from": "MAA", "to": "DXB", "date": "2026-04-05", "price": 260, "airline": "IndiGo", "departure": "12:00", "arrival": "14:30", "duration": "4h"},
    
    # Other international routes
    {"id": "F021", "from": "NYC", "to": "LON", "date": "2025-08-12", "price": 750, "airline": "British Airways", "departure": "19:00", "arrival": "07:00", "duration": "7h"},
    {"id": "F022", "from": "NYC", "to": "SFO", "date": "2025-08-12", "price": 320, "airline": "United", "departure": "09:00", "arrival": "12:00", "duration": "6h"},
    {"id": "F023", "from": "DEL", "to": "DXB", "date": "2025-09-01", "price": 280, "airline": "Air India", "departure": "10:00", "arrival": "12:00", "duration": "3h 30m"},
    {"id": "F024", "from": "DEL", "to": "NYC", "date": "2025-09-10", "price": 900, "airline": "Air India", "departure": "01:00", "arrival": "07:00", "duration": "15h"},
    
    # NYC to London - December 2025
    {"id": "F028", "from": "NYC", "to": "LON", "date": "2025-12-08", "price": 780, "airline": "British Airways", "departure": "20:00", "arrival": "08:00", "duration": "7h"},
    {"id": "F029", "from": "NYC", "to": "LON", "date": "2025-12-08", "price": 720, "airline": "Virgin Atlantic", "departure": "22:00", "arrival": "10:00", "duration": "7h"},
    {"id": "F030", "from": "NYC", "to": "LON", "date": "2025-12-08", "price": 850, "airline": "American Airlines", "departure": "18:00", "arrival": "06:00", "duration": "7h"},
    
    # London (LHR) to New York (NYC) - December 25, 2025
    {"id": "F031", "from": "LHR", "to": "NYC", "date": "2025-12-25", "price": 820, "airline": "British Airways", "departure": "10:00", "arrival": "13:00", "duration": "7h"},
    {"id": "F032", "from": "LHR", "to": "NYC", "date": "2025-12-25", "price": 750, "airline": "Virgin Atlantic", "departure": "12:00", "arrival": "15:00", "duration": "7h"},
    {"id": "F033", "from": "LHR", "to": "NYC", "date": "2025-12-25", "price": 890, "airline": "American Airlines", "departure": "14:00", "arrival": "17:00", "duration": "7h"},
    {"id": "F034", "from": "LHR", "to": "NYC", "date": "2025-12-25", "price": 680, "airline": "Norwegian Air", "departure": "16:00", "arrival": "19:00", "duration": "7h"},
    {"id": "F035", "from": "LHR", "to": "NYC", "date": "2025-12-25", "price": 950, "airline": "Delta", "departure": "18:00", "arrival": "21:00", "duration": "7h"},
    {"id": "F036", "from": "LHR", "to": "NYC", "date": "2025-12-25", "price": 720, "airline": "United Airlines", "departure": "20:00", "arrival": "23:00", "duration": "7h"},
    
    # Hyderabad (HYD) to Dubai (DXB)
    {"id": "F025", "from": "HYD", "to": "DXB", "date": "2026-04-01", "price": 310, "airline": "Emirates", "departure": "05:30", "arrival": "08:00", "duration": "4h"},
    {"id": "F026", "from": "HYD", "to": "DXB", "date": "2026-04-05", "price": 255, "airline": "IndiGo", "departure": "11:00", "arrival": "13:30", "duration": "4h"},
    {"id": "F027", "from": "HYD", "to": "DXB", "date": "2026-04-10", "price": 285, "airline": "Air India", "departure": "16:00", "arrival": "18:30", "duration": "4h"},
]
