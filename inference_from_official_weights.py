import os
import pprint
import numpy as np
import tensorflow as tf
import cv2

from network_v2.generator import generator


def variables_to_restore():
    lod = int(np.log2(1024))
    t_vars = tf.trainable_variables()
    var_mapping = dict()

    for v in t_vars:
        current_var_name = v.name
        current_var_name = current_var_name.split(':', 1)[0]
        current_splitted = current_var_name.split('/')
        prefix_1 = current_splitted[0]
        possible_torgb_body = current_splitted[2]
        if '_mapping' in prefix_1:
            official_var_name = 'G_mapping/'
        else:
            official_var_name = 'G_synthesis/'

        if 'ToRGB' in possible_torgb_body:
            res = int(current_splitted[1].split('x', 1)[0])
            cur_lod = lod - int(np.log2(res))
            official_var_name += 'ToRGB_lod{}/{}'.format(cur_lod, current_splitted[-1])
        else:
            official_var_name += '/'.join(current_splitted[1:])

        var_mapping[official_var_name] = v

    with tf.variable_scope('', reuse=True):
        var_mapping['G/dlatent_avg'] = tf.get_variable('w_avg')
    return var_mapping


def test_generator():
    # prepare variables & construct generator
    image_out_dir = './assets'
    is_training = False
    z_dim = 512
    g_params = {
        'w_dim': 512,
        'n_mapping': 8,
        'resolutions': [4, 8, 16, 32, 64, 128, 256, 512, 1024],
        'featuremaps': [512, 512, 512, 512, 256, 128, 64, 32, 16],
        'w_ema_decay': 0.995,
        'style_mixing_prob': 0.9,
        'truncation_psi': 0.7,
        'truncation_cutoff': 8,
    }
    z = tf.placeholder(tf.float32, shape=[None, z_dim], name='z')
    alpha = tf.get_variable('alpha', shape=[], dtype=tf.float32, initializer=tf.initializers.zeros(), trainable=False)
    fake_images = generator(z, alpha, g_params, is_training)

    # assign which variables to retore
    var_mapping = variables_to_restore()
    pprint.pprint(var_mapping)

    # restore tools
    model_dir = './official-pretrained'
    ckpt_name = 'model.ckpt'
    model_ckpt = os.path.join(model_dir, ckpt_name)
    saver = tf.train.Saver(var_list=var_mapping)

    # set same input status as official's
    rnd = np.random.RandomState(5)
    z_input_np = rnd.randn(1, z_dim)
    drange_min, drange_max = -1.0, 1.0
    scale = 255.0 / (drange_max - drange_min)

    # generate image with official weights
    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())
        saver.restore(sess, model_ckpt)

        output = sess.run(fake_images, feed_dict={z: z_input_np})
        print(output.shape)

        output = np.squeeze(output, axis=0)
        output = np.transpose(output, axes=[1, 2, 0])
        output = output * scale + (0.5 - drange_min * scale)
        output = np.clip(output, 0, 255)
        output = output.astype('uint8')
        output = cv2.cvtColor(output, cv2.COLOR_RGB2BGR)

        out_fn = os.path.join(image_out_dir, 'from-official-weights.png')
        cv2.imwrite(out_fn, output)
    return


def main():
    test_generator()
    return


if __name__ == '__main__':
    main()