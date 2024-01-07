from sqlalchemy import Column, Integer, Boolean, String, ForeignKey, Table, select
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from sqlalchemy.sql import Selectable
from sqlalchemy.orm import sessionmaker

DATABASE_URI = 'sqlite:///instance/e621.db'
engine = create_engine(DATABASE_URI)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class ViewedList(Base):
    __tablename__ = 'viewed_list'
    image_id = Column(Integer, primary_key=True)
    is_favorited = Column(Boolean)
    is_viewed = Column(Boolean)
    my_vote = Column(Integer)
    created_at = Column(String(50))
    tags = relationship('Tag', secondary='image_tag', back_populates='images')
    community_stats = relationship('CommunityStats', uselist=False, back_populates='viewed_image')

class Tag(Base):
    __tablename__ = 'tag'
    tag_id = Column(Integer, primary_key=True)
    tag_name = Column(String, nullable=False)
    tag_type = Column(String, nullable=False)  
    images = relationship('ViewedList', secondary='image_tag', back_populates='tags')

class CommunityStats(Base):
    __tablename__ = 'community_stats'
    image_id = Column(Integer, ForeignKey('viewed_list.image_id'), primary_key=True)
    rating = Column(String(1), nullable=False)
    type = Column(String(10), nullable=False)
    fav_count = Column(Integer, nullable=False)
    up_votes = Column(Integer, nullable=False)
    down_votes = Column(Integer, nullable=False)
    total_score = Column(Integer, nullable=False)
    comment_count = Column(Integer, nullable=False)
    viewed_image = relationship('ViewedList', back_populates='community_stats')

image_tag = Table('image_tag', Base.metadata,
    Column('image_id', Integer, ForeignKey('viewed_list.image_id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tag.tag_id'), primary_key=True)
)

#-----------------------------------------------------------------------
# functions
#-----------------------------------------------------------------------

def init_db(app):
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
    Base.metadata.create_all(engine)

def filter_results(response_json):
    with Session() as session:
        for post in response_json['posts']:
            post_id = post['id']
            is_favorited = post['is_favorited']
            created_at = post['created_at']
            tags = post['tags']

            my_vote = 0 
            is_hidden = False

            viewed_image = session.get(ViewedList, post_id)

            if not viewed_image:
                viewed_image = ViewedList(
                    image_id=post_id, 
                    created_at=created_at, 
                    is_favorited=is_favorited, 
                    is_viewed=False, 
                    my_vote=0
                )
                session.add(viewed_image)
                session.commit()
            else:
                my_vote = viewed_image.my_vote
                is_hidden = viewed_image.is_viewed
                #inject some db data fields for the front end
                #if no post.score.my_vote then it will be highighted as a new post
                post['score']['my_vote'] = my_vote
                post['is_hidden'] = is_hidden

            image_stats = CommunityStats(
                image_id=post_id, 
                rating=post['rating'], 
                type=post['file']['ext'],
                fav_count=post['fav_count'], 
                up_votes=post['score']['up'], 
                down_votes=post['score']['up'], 
                total_score=post['score']['total'],
                comment_count=post['comment_count']
            )
            process_stats(session, image_stats)
            process_tags(session, tags, viewed_image)

def process_stats(session, image_stats):
    existing_entry = session.get(CommunityStats, image_stats.image_id)
    if existing_entry:
        existing_entry.rating = image_stats.rating
        existing_entry.type = image_stats.type
        existing_entry.fav_count = image_stats.fav_count
        existing_entry.up_votes = image_stats.up_votes
        existing_entry.down_votes = image_stats.down_votes
        existing_entry.total_score = image_stats.total_score
        existing_entry.comment_count = image_stats.comment_count
    else:
        session.add(image_stats)
    
    session.commit()
    
def process_tags(session, tags, viewed_image):
    # Prepare sets for comparison
    new_tags = {(tag_name, tag_type) for tag_type, tag_list in tags.items() for tag_name in tag_list}
    current_tags = {(tag.tag_name, tag.tag_type) for tag in viewed_image.tags}

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
            viewed_image.tags.remove(tag)

    # Process additions
    for tag_name, tag_type in tags_to_add:
        tag = fetched_tags.get((tag_name, tag_type))
        if not tag:
            tag = Tag(tag_name=tag_name, tag_type=tag_type)
            session.add(tag)
            fetched_tags[(tag_name, tag_type)] = tag
        viewed_image.tags.append(tag)

    session.commit()

def set_vote(image_id, vote_score):
    with Session() as session:
        entry = session.query(ViewedList).filter_by(image_id=image_id).first()
        if entry:
            entry.my_vote = vote_score

def set_hidden(image_id, is_hidden):
    with Session() as session:
        entry = session.query(ViewedList).filter_by(image_id=image_id).first()
        if entry:
            entry.is_viewed = is_hidden

def get_entry(session: Session, stmt: Selectable):
    result = session.execute(stmt)
    return result.scalars().first()

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
