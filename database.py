from sqlalchemy import Column, Integer, Boolean, String, ForeignKey, Table, select
from sqlalchemy import create_engine, DateTime
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from sqlalchemy.sql import Selectable
import pandas as pd
from datetime import datetime, timedelta
import re

DATABASE_URI = 'sqlite:///instance/e621.db'
engine = create_engine(DATABASE_URI)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class Post(Base):
    __tablename__ = 'posts'
    image_id = Column(Integer, primary_key=True)
    uploader_id = Column(Integer)
    approver_id = Column(Integer)
    created_at = Column(DateTime)
    rating = Column(String(1))
    description = Column(String)
    file_ext = Column(String)
    file_size = Column(Integer)
    parent_id = Column(Integer)
    change_seq = Column(Integer)
    is_deleted = Column(Boolean)
    is_pending = Column(Boolean)
    comment_count = Column(Integer)
    fav_count = Column(Integer)
    score = Column(Integer)
    up_score = Column(Integer)
    down_score = Column(Integer)
    preview_url = Column(String, default='')  
    file_url = Column(String, default='') 
    tags = relationship('Tag', secondary='image_tag', back_populates='images')

class Tag(Base):
    __tablename__ = 'tags'
    tag_id = Column(Integer, primary_key=True)
    tag_name = Column(String, nullable=False)
    tag_type = Column(String, nullable=False)  
    images = relationship('Post', secondary='image_tag', back_populates='tags')

class Stats(Base):
    __tablename__ = 'stats'
    image_id = Column(Integer, ForeignKey('posts.image_id'), primary_key=True)
    is_favorited = Column(Boolean, default=False, nullable=False)
    my_vote = Column(Integer, default=0, nullable=False)

image_tag = Table('image_tag', Base.metadata,
    Column('image_id', Integer, ForeignKey('posts.image_id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.tag_id'), primary_key=True)
)

def init_db(app):
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
    Base.metadata.create_all(engine)

#-----------------------------------------------------------------------
# Populate from e621 db_export .csv files
#-----------------------------------------------------------------------
    
def populate_db():
    def parse_date(date_str):
        try:
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")

    file_path = 'posts-2024-01-07.csv'
    chunk_size = 10000 
    with Session() as session:
        for chunk in pd.read_csv(file_path, chunksize=chunk_size):
            first_entry_date = chunk.iloc[0]['created_at']
            print(f"chunk starting date: {first_entry_date}")
            for index, row in chunk.iterrows():
                is_deleted = True if row['is_deleted'] == 't' else False
                is_pending = True if row['is_pending'] == 't' else False
                date_time = parse_date(row['created_at'])
                post = Post(
                    image_id=row['id'],
                    uploader_id=row['uploader_id'],
                    approver_id=row['approver_id'],
                    created_at=date_time,
                    rating=row['rating'],
                    description=row['description'],
                    file_ext=row['file_ext'],
                    file_size=row['file_size'],
                    parent_id=row['parent_id'],
                    change_seq=row['change_seq'],
                    is_deleted=is_deleted,
                    is_pending=is_pending,
                    comment_count=row['comment_count'],
                    fav_count=row['fav_count'],
                    score=row['score'],
                    up_score=row['up_score'],
                    down_score=row['down_score']
                )
                session.add(post)
            session.commit()
    print("Done!")

def harvest_old_db_data():

    return

#-----------------------------------------------------------------------
# functions
#-----------------------------------------------------------------------

def filter_results(response_json):
    with Session() as session:
        for post in response_json['posts']:
            post_id = post['id']
            is_favorited = post['is_favorited']
            tags = post['tags']

            stats_entry = session.get(Stats, post_id)
            if stats_entry:
                #inject my_vote, else it will be highighted as a new post
                post['score']['my_vote'] = stats_entry.my_vote

                if(is_favorited != stats_entry.is_favorited):
                    stats_entry.is_favorited = is_favorited
            else:
                stats_entry = Stats(image_id=post_id, is_favorited=is_favorited)
                session.add(stats_entry)

            db_entry = session.get(Post, post_id)
            if not db_entry:
                db_entry = Post(image_id = post_id,
                    uploader_id = post['uploader_id'],
                    approver_id = post['approver_id'],
                    created_at = convert_to_datetime(post['created_at']), 
                    rating = post['rating'],
                    description = post['description'],
                    file_ext = post['file']['ext'],
                    file_size = post['file']["size"],
                    parent_id = post['relationships']['parent_id'],
                    change_seq = post['change_seq'],
                    is_deleted = post['flags']['deleted'],
                    is_pending = post['flags']['pending'],
                    comment_count = post['comment_count'],
                    fav_count = post['fav_count'],
                    score = post['score']['total'],
                    up_score = post['score']['up'],
                    down_score = post['score']['down'],
                    preview_url = post['preview']['url'],  
                    file_url = post['file']['url']
                )
                session.add(db_entry)
                session.commit()

            process_tags(session, tags, db_entry)
    
def process_tags(session, tags, db_entry):
    # Prepare sets for comparison
    new_tags = {(tag_name, tag_type) for tag_type, tag_list in tags.items() for tag_name in tag_list}
    current_tags = {(tag.tag_name, tag.tag_type) for tag in db_entry.tags}

    # Determine tags to add and remove
    tags_to_add = new_tags - current_tags
    tags_to_remove = current_tags - new_tags

    # Fetch all relevant tags in one query
    all_relevant_tag_names = {tag[0] for tag in tags_to_add.union(tags_to_remove)}
    stmt = select(Tag).where(Tag.tag_name.in_(all_relevant_tag_names))
    fetched_tags = { (tag.tag_name, tag.tag_type): tag for tag in session.execute(stmt).scalars() }

    # Process removals
    for tag_name, tag_type in tags_to_remove:
        tag = fetched_tags.get((tag_name, tag_type))
        if tag:
            db_entry.tags.remove(tag)

    # Process additions
    for tag_name, tag_type in tags_to_add:
        tag = fetched_tags.get((tag_name, tag_type))
        if not tag:
            tag = Tag(tag_name=tag_name, tag_type=tag_type)
            session.add(tag)
            fetched_tags[(tag_name, tag_type)] = tag
        db_entry.tags.append(tag)

    session.commit()

def set_vote(image_id, vote_score):
    with Session() as session:
        entry = session.get(Stats, image_id)
        if (entry.my_vote != vote_score):
            entry.my_vote = vote_score

def set_favorite(image_id, is_favorited):
    with Session() as session:
        entry = session.get(Stats, image_id)
        if(entry.is_favorited != is_favorited):
            entry.is_favorited = is_favorited

def raw_query(query):
    result = {}
    with Session() as session:  
        result_data = session.execute(query)
        rows = result_data.fetchall()
        columns = result_data.keys()
        
        result = {
            'columns': [col for col in columns],
            'rows': [dict(zip(columns, row)) for row in rows]
        }
    return result

def convert_to_datetime(input_str):
    # Regex pattern to match the format
    pattern = r'(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2}\.\d+)([+-]\d{2}:\d{2})'
    match = re.match(pattern, input_str)

    print(input_str)

    if not match:
        raise ValueError("Invalid format for datetime string")

    date_part, time_part, tz_offset = match.groups()

    # Combine date and time parts
    datetime_part = f"{date_part} {time_part}"

    date_time = datetime.strptime(datetime_part, "%Y-%m-%d %H:%M:%S.%f")
    tz_sign = '+' if tz_offset.startswith('+') else '-'
    tz_hours, tz_minutes = map(int, tz_offset[1:].split(':'))
    if tz_sign == '+':
        date_time -= timedelta(hours=tz_hours, minutes=tz_minutes)
    else:
        date_time += timedelta(hours=tz_hours, minutes=tz_minutes)

    return date_time