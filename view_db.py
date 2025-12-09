#!/usr/bin/env python3
"""
Simple script to view SQLite database contents.
Usage: python view_db.py
"""
import json
from pathlib import Path
from sqlmodel import Session, select
from database.connection import engine
from database.models import Itinerary, ChatHistory

def print_itineraries():
    """Print all itineraries in a readable format."""
    with Session(engine) as session:
        query = select(Itinerary).order_by(Itinerary.created_at.desc())
        itineraries = session.exec(query).all()
        
        if not itineraries:
            print("No itineraries found.")
            return
        
        print(f"\n{'='*80}")
        print(f"ITINERARIES ({len(itineraries)} total)")
        print(f"{'='*80}\n")
        
        for it in itineraries:
            print(f"ID: {it.id}")
            print(f"Traveler: {it.traveler_id}")
            print(f"Status: {it.status}")
            print(f"Version: {it.version}")
            print(f"Total Cost: ${it.total_cost:.2f}")
            print(f"Created: {it.created_at}")
            print(f"Updated: {it.updated_at}")
            
            if it.original_query:
                print(f"Original Query: {it.original_query[:60]}...")
            
            if it.flight_data:
                print(f"Flight: {json.dumps(it.flight_data, indent=2)}")
            if it.hotel_data:
                print(f"Hotel: {json.dumps(it.hotel_data, indent=2)}")
            if it.car_data:
                print(f"Car: {json.dumps(it.car_data, indent=2)}")
            
            print(f"{'-'*80}\n")


def print_chat_history():
    """Print all chat history."""
    with Session(engine) as session:
        query = select(ChatHistory).order_by(ChatHistory.created_at.desc())
        messages = session.exec(query).all()
        
        if not messages:
            print("No chat history found.")
            return
        
        print(f"\n{'='*80}")
        print(f"CHAT HISTORY ({len(messages)} messages)")
        print(f"{'='*80}\n")
        
        for msg in messages:
            print(f"[{msg.created_at}] {msg.role.upper()}: {msg.content}")
            print(f"  Itinerary: {msg.itinerary_id}")
            print()


def print_summary():
    """Print database summary."""
    with Session(engine) as session:
        itinerary_count = len(list(session.exec(select(Itinerary)).all()))
        chat_count = len(list(session.exec(select(ChatHistory)).all()))
        
        # Count by status
        draft_count = len(list(session.exec(select(Itinerary).where(Itinerary.status == "draft")).all()))
        confirmed_count = len(list(session.exec(select(Itinerary).where(Itinerary.status == "confirmed")).all()))
        cancelled_count = len(list(session.exec(select(Itinerary).where(Itinerary.status == "cancelled")).all()))
        
        print(f"\n{'='*80}")
        print("DATABASE SUMMARY")
        print(f"{'='*80}")
        print(f"Itineraries: {itinerary_count}")
        print(f"  - Draft: {draft_count}")
        print(f"  - Confirmed: {confirmed_count}")
        print(f"  - Cancelled: {cancelled_count}")
        print(f"Chat Messages: {chat_count}")
        print(f"{'='*80}\n")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "summary":
            print_summary()
        elif sys.argv[1] == "chat":
            print_chat_history()
        elif sys.argv[1] == "itineraries":
            print_itineraries()
        else:
            print("Usage: python view_db.py [summary|itineraries|chat]")
    else:
        # Print everything
        print_summary()
        print_itineraries()
        print_chat_history()

