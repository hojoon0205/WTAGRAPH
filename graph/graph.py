import random
import dgl
import torch as th
import numpy as np
import pickle

class GraphLoader:
    def __init__(self):
        pass

    def load_node_edge_map(self, args):
        db_name = args.db_name if args.db_name.endswith('/') else args.db_name + '/'

        id_node_map_path = './data/graph_data/'  + db_name + args.graph_name  + '_id_node_map.pickle'
        with open(id_node_map_path, 'rb') as f:  id_node_map = pickle.load(f)

        id_edge_map_list_path = './data/graph_data/' + db_name + args.graph_name  + '_id_edge_map_list.pickle'
        with open(id_edge_map_list_path, 'rb') as f: id_edge_map = pickle.load(f)

        return id_node_map, id_edge_map

    def load_graph(self, args):
        print('\n************loading the specified graph and feature data************')
        #------ 1. load graph.edgelist to rebuild the graph
        edgelist_path = './data/graph_data/' + args.db_name + '/' + args.graph_name + '_graph.edgelist'
        with open(edgelist_path, 'r') as f:
            edges = [tuple(line.strip().split(',')) for line in f]
            #format: e.g. 26,5350,3982
        edges = [tuple((int(e[0]), int(e[1]), int(e[2]))) for e in edges]
        src_nodes = [e[1] for e in edges]
        dst_nodes = [e[2] for e in edges]
        # print("edges", len(edges), 'src_nodes', len(set(src_nodes)), 'dst_nodes', len(set(dst_nodes)))

        #------ 2. rebuild the dgl graph
        g = dgl.DGLGraph().to('cuda:0')
        g.add_nodes(len(set(src_nodes).union(set(dst_nodes))))
        g.add_edges(src_nodes, dst_nodes)
        print('Loaded graph: ', args.db_name, args.graph_name, g,'\n')

        #------ 3. load node feature
        nf = np.load('./data/feat_data/'  + args.db_name + '/' + args.graph_name + '_node_feat.npy')
        nf = th.from_numpy(nf).to('cuda:0')
        print('node feature shape:', nf.shape)
        
        #------ 4. load edge feature
        ef = np.load('./data/feat_data/'  + args.db_name + '/' + args.graph_name + '_edge_feat.npy')
        ef = th.from_numpy(ef).to('cuda:0')
        print('edge feature shape:', ef.shape)

        #------ 5. load edge label
        e_label = np.load('./data/feat_data/'  + args.db_name + '/' + args.graph_name + '_edge_label.npy').tolist()
        e_label = th.tensor(e_label).to('cuda:0')
        print('edge labels shape:', e_label.shape)

        #------ 6. prepare train test val mask
        train_mask, test_mask, val_mask = self._split_dataset(e_label, (args.r_train, args.r_test, args.r_val))

        print('***************************loading completed***************************\n')
        return g, nf, ef, e_label, train_mask, test_mask, val_mask

    def _split_dataset(self, labels, ratio_tuple):   
        shuffle_list = [i for i in range(labels.shape[0])]
        random.shuffle(shuffle_list)
        train_ct = int(len(shuffle_list) * ratio_tuple[0])
        test_ct =  int(len(shuffle_list) * ratio_tuple[1])
        val_ct =   int(len(shuffle_list) * ratio_tuple[2])
        print('# of train edge:', train_ct, '   # of test edge:', test_ct, ' # of val edge:', val_ct)

        train_mask = np.zeros(labels.shape[0])
        test_mask = np.zeros(labels.shape[0])
        val_mask = np.zeros(labels.shape[0])
        for idx in range(0, train_ct):
            train_mask[shuffle_list[idx]] = 1
        for idx in range(train_ct, train_ct + test_ct):
            test_mask[shuffle_list[idx]] = 1
        for idx in range(len(shuffle_list) - val_ct, len(shuffle_list)):
            val_mask[shuffle_list[idx]] = 1

        train_mask = th.BoolTensor(train_mask)
        test_mask = th.BoolTensor(test_mask)
        val_mask = th.BoolTensor(val_mask)

        ### print stats of tracking in each split
        # track_in_train = th.sum(1 == labels[train_mask])
        # track_in_test = th.sum(1 == labels[test_mask])
        # track_in_val = th.sum(1 == labels[val_mask])
        # print(track_in_train, track_in_test, track_in_val) 
        # print("{:.2f}".format(track_in_train.item() * 1.0 / train_ct),
        #     "{:.2f}".format(track_in_test.item() * 1.0 / test_ct),
        #     "{:.2f}".format(track_in_val.item() * 1.0 / val_ct))

        return train_mask, test_mask, val_mask

