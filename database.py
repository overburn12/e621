from sqlalchemy import Column, Integer, Boolean, String, ForeignKey, Table, select
from sqlalchemy import create_engine, DateTime, Index
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from datetime import datetime, timedelta
import re, time

DATABASE_URI = 'sqlite:///instance/ramdisk/e621.db'
engine = create_engine(DATABASE_URI)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class Post(Base):
    #the images of the image board
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
    change_seq = Column(Integer) #increases any time the entry is updated/changed
    is_deleted = Column(Boolean)
    is_pending = Column(Boolean)
    comment_count = Column(Integer)
    fav_count = Column(Integer)
    score = Column(Integer) # total score overall (downvotes+upvotes)
    up_score = Column(Integer) # total upvotes count
    down_score = Column(Integer) # total downvotes count
    preview_url = Column(String, default='')  
    file_url = Column(String, default='') 
    tags = relationship('Tag', secondary='image_tag', back_populates='images')

class Tag(Base):
    #tags for the images. note: if tag_type='artist' then tag_name=artists name
    __tablename__ = 'tags'
    tag_id = Column(Integer, primary_key=True)
    tag_name = Column(String, nullable=False)
    tag_type = Column(String, nullable=False)  
    images = relationship('Post', secondary='image_tag', back_populates='tags')

class Stats(Base):
    #used to track my personal interactions with the image board
    __tablename__ = 'stats'
    image_id = Column(Integer, ForeignKey('posts.image_id'), primary_key=True)
    is_favorited = Column(Boolean, default=False, nullable=False)
    my_vote = Column(Integer, default=0, nullable=False) # -1 = down vote, 0 = no vote, 1 = upvote

image_tag = Table('image_tag', Base.metadata,
    Column('image_id', Integer, ForeignKey('posts.image_id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tags.tag_id'), primary_key=True)
)

from sqlalchemy.orm import validates

class TagCooccurrence(Base):
    __tablename__ = 'tag_cooccurrences'
    tag1_id = Column(Integer, ForeignKey('tags.tag_id'), primary_key=True)
    tag2_id = Column(Integer, ForeignKey('tags.tag_id'), primary_key=True)
    cooccurrence_count = Column(Integer, default=0)

    __table_args__ = (
        Index('idx_cooccurrence_tags', 'tag1_id', 'tag2_id'),
        Index('idx_cooccurrence_count', 'cooccurrence_count'),
    )

    @validates('tag1_id', 'tag2_id')
    def validate_tag_ids(self, key, tag_id):
        if key == 'tag2_id' and self.tag1_id:
            assert tag_id > self.tag1_id, "tag2_id must be greater than tag1_id"
        return tag_id
#-----------------------------------------------------------------------
# tags_dict functions 
#-----------------------------------------------------------------------
        
tags_dict = {}

def init_tags_dict():
    print('loading DB tags...')
    start_time = time.time()
    total_tags = 0

    if not tags_dict:
        with Session() as session:
            all_tags = session.query(Tag).all()
            for tag in all_tags:
                tag_key = (tag.tag_name, tag.tag_type)
                tags_dict[tag_key] = tag
                total_tags += 1
    else:
        print('tags already loaded')
        
    delta_time = time.time() - start_time
    tag_rate = total_tags / delta_time
    print(f'tags: {total_tags}, time: {delta_time:.2f} seconds, rate: {tag_rate:.0f} tags/sec')

#-----------------------------------------------------------------------
# api functions
#-----------------------------------------------------------------------

def filter_results(response_json, do_stats = True):
    with Session() as session:
        for post in response_json['posts']:
            post_id = post['id']
            is_favorited = post['is_favorited']
            tags = post['tags']

            if do_stats or is_favorited:
                stats_entry = session.get(Stats, post_id)
                if stats_entry:
                    #inject my_vote, else it will be highighted as a new post
                    post['score']['my_vote'] = stats_entry.my_vote

                    if(is_favorited != stats_entry.is_favorited):
                        stats_entry.is_favorited = is_favorited
                else:
                    stats_entry = Stats(image_id=post_id, is_favorited=is_favorited)
                    session.add(stats_entry)

            db_entry = proccess_post(session, post)
            process_tags(session, db_entry, tags)
        session.commit()

def proccess_post(session, post):
    db_entry = session.get(Post, post['id'])
    if db_entry:
        if db_entry.change_seq < post['change_seq']: 
            db_entry.uploader_id = post['uploader_id']
            db_entry.approver_id = post['approver_id']
            db_entry.created_at = convert_to_datetime(post['created_at'])
            db_entry.rating = post['rating']
            db_entry.description = post['description']
            db_entry.file_ext = post['file']['ext']
            db_entry.file_size = post['file']['size']
            db_entry.parent_id = post['relationships']['parent_id']
            db_entry.change_seq = post['change_seq']
            db_entry.is_deleted = post['flags']['deleted']
            db_entry.is_pending = post['flags']['pending']
            db_entry.comment_count = post['comment_count']
            db_entry.fav_count = post['fav_count']
            db_entry.score = post['score']['total']
            db_entry.up_score = post['score']['up']
            db_entry.down_score = post['score']['down']
            db_entry.preview_url = post['preview']['url']
            db_entry.file_url = post['file']['url']
    else:    
        db_entry = Post(image_id = post['id'],
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
    return db_entry

def process_tags(session, db_entry, tags):
    new_tags = {(tag_name, tag_type) for tag_type, tag_list in tags.items() for tag_name in tag_list}
    current_tags = {(tag.tag_name, tag.tag_type) for tag in db_entry.tags}

    tags_to_add = new_tags - current_tags
    tags_to_remove = current_tags - new_tags

    # Process tag creation
    for tag_name, tag_type in new_tags:
        tag = tags_dict.get((tag_name, tag_type))
        if not tag:
            tag = Tag(tag_name=tag_name, tag_type=tag_type)
            tags_dict[(tag_name, tag_type)] = tag
            session.add(tag)

    # Process removals
    for tag_name, tag_type in tags_to_remove:
        tag = tags_dict.get((tag_name, tag_type))
        db_entry.tags.remove(tag)

    # Process additions
    for tag_name, tag_type in tags_to_add:
        try:
            tag = tags_dict.get((tag_name, tag_type))
            db_entry.tags.append(tag)

            if False:
                # Update cooccurrences for each tag pair
                for existing_tag in db_entry.tags:
                    if existing_tag != tag:
                        cooccur_entry = session.query(TagCooccurrence).filter(
                            ((TagCooccurrence.tag1_id == existing_tag.tag_id) & (TagCooccurrence.tag2_id == tag.tag_id)) |
                            ((TagCooccurrence.tag1_id == tag.tag_id) & (TagCooccurrence.tag2_id == existing_tag.tag_id))
                        ).first()

                        min_tag_id = min(existing_tag.tag_id, tag.tag_id)
                        max_tag_id = max(existing_tag.tag_id, tag.tag_id)
                        
                        if cooccur_entry:
                            cooccur_entry.cooccurrence_count += 1
                        else:
                            session.add(TagCooccurrence(tag1_id=min_tag_id, tag2_id=max_tag_id, cooccurrence_count=1))
 
        except Exception as e:
            print(f"Error occurred with tag_name: {tag_name}, tag_type: {tag_type}")
            print(f"Error details: {e}")

#-----------------------------------------------------------------------
# Stats functions
#-----------------------------------------------------------------------

def set_vote(image_id, vote_score):
    with Session() as session:
        entry = session.get(Stats, image_id)
        if (entry.my_vote != vote_score):
            entry.my_vote = vote_score
            session.commit()

def set_favorite(image_id, is_favorited):
    with Session() as session:
        entry = session.get(Stats, image_id)
        if(entry.is_favorited != is_favorited):
            entry.is_favorited = is_favorited
            session.commit()

#-----------------------------------------------------------------------
# other functions
#-----------------------------------------------------------------------

def init_db(app = None):
    if app:
        app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
    Base.metadata.create_all(engine)
    init_tags_dict()

def raw_query(query):
    result = {}
    with Session() as session:  
        result_data = session.execute(query)
        
        if result_data:
            rows = result_data.fetchall()
            columns = result_data.keys()
            result = {
                'columns': [col for col in columns],
                'rows': [dict(zip(columns, row)) for row in rows]
            }
        else:
            result = {
                'columns': ['no results'],
                'rows': ['N/A']
            }
        session.commit()
    return result

def convert_to_datetime(input_str):
    #this converts API response datetime
    pattern = r'(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2}\.\d+)([+-]\d{2}:\d{2})'
    match = re.match(pattern, input_str)

    if not match:
        raise ValueError("Invalid format for datetime string")

    date_part, time_part, tz_offset = match.groups()
    datetime_part = f"{date_part} {time_part}"

    date_time = datetime.strptime(datetime_part, "%Y-%m-%d %H:%M:%S.%f")
    tz_sign = '+' if tz_offset.startswith('+') else '-'
    tz_hours, tz_minutes = map(int, tz_offset[1:].split(':'))
    if tz_sign == '+':
        date_time -= timedelta(hours=tz_hours, minutes=tz_minutes)
    else:
        date_time += timedelta(hours=tz_hours, minutes=tz_minutes)

    return date_time