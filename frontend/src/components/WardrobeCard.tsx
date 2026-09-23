import { Link } from 'react-router-dom';
import type { WardrobeItem } from '../types';
import { imageUrl } from '../services/api';

interface Props {
  item: WardrobeItem;
  onDelete?: (id: number) => void;
}

export function WardrobeCard({ item, onDelete }: Props) {
  return (
    <article className="wardrobe-card">
      <Link to={`/wardrobe/${item.id}`}>
        <img src={imageUrl(item.image_url)} alt={`${item.colour} ${item.type}`} />
        <div className="body">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span className="badge badge-muted">{item.wardrobe_code}</span>
          </div>
          <h3 style={{ marginTop: 8 }}>
            {item.colour} {item.type}
          </h3>
          <p className="meta">
            {item.category} · {item.pattern} · {item.style.replace(/_/g, ' ')}
          </p>
        </div>
      </Link>
      {onDelete && (
        <div className="body" style={{ paddingTop: 0 }}>
          <button type="button" className="btn btn-danger" style={{ width: '100%' }} onClick={() => onDelete(item.id)}>
            Delete
          </button>
        </div>
      )}
    </article>
  );
}
